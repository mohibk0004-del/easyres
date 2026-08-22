import sys
import os
import ctypes
import threading
import urllib.request
import json
import webbrowser

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QGraphicsDropShadowEffect, QGridLayout, QComboBox, 
    QLineEdit, QSizeGrip, QSystemTrayIcon, QMenu, QScrollArea, QMessageBox, QCheckBox, QPushButton
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSettings, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QIntValidator, QIcon, QPixmap

from theme import tokens as t
from theme import styles
from ui.widgets import PremiumToggle, ActionButton, IconButton, SectionLabel, ResolutionHero, PresetCard
from ui.dialogs import SettingsDialog, TutorialDialog, themed_message_box
import resolution
import edid
import driver

APP_VERSION = "2.1.4"
WM_HOTKEY = 0x0312
HOTKEY_ID_TOGGLE = 1
DEFAULT_HOTKEY_VK = 0x75

def is_newer_version(latest, current):
    try:
        l_parts = [int(x) for x in latest.split('.')]
        c_parts = [int(x) for x in current.split('.')]
        return l_parts > c_parts
    except:
        return latest != current

from ctypes import wintypes
from PyQt6.QtCore import QAbstractNativeEventFilter

class HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, eventType, message):
        if eventType not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_TOGGLE:
            self.callback()
            return True, 0
        return False, 0

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
            d['device_id'] = d.get('device_id')
        self.current_display = self.displays[0] if self.displays else None
        self._preset_cache = {}
        self._preset_retry_pending = set()
        self.settings = QSettings("EasyRes", "App")
        self.hotkey_filter = None
        self.hotkey_registered = False
        self.last_stretch_modes = self._load_last_stretch_modes()
        
        self.init_ui()
        self.init_hotkey()
        self.refresh_display()
        self.load_presets()
        
        QTimer.singleShot(500, self.check_first_run)
        self.update_available.connect(self.show_update_notification)
        threading.Thread(target=self.check_for_updates_background, daemon=True).start()
        
        self.setWindowOpacity(0.0)
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(t.MOTION_FADE)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.opacity_anim.start()

    def _load_last_stretch_modes(self):
        raw = self.settings.value("last_stretch_modes", {}, type=dict)
        if isinstance(raw, dict):
            return raw
        return {}

    def _save_last_stretch_modes(self):
        self.settings.setValue("last_stretch_modes", self.last_stretch_modes)

    def init_hotkey(self):
        app = QApplication.instance()
        self.hotkey_filter = HotkeyEventFilter(self.toggle_stretch_native_hotkey)
        app.installNativeEventFilter(self.hotkey_filter)
        self.apply_hotkey_setting()

    def get_hotkey_config(self):
        vk = self.settings.value("toggle_hotkey_vk", DEFAULT_HOTKEY_VK, type=int)
        valid_vks = range(0x70, 0x7C)
        if not isinstance(vk, int) or vk not in valid_vks:
            vk = DEFAULT_HOTKEY_VK
            self.settings.setValue("toggle_hotkey_vk", vk)
        name = f"F{vk - 0x70 + 1}"
        self.settings.setValue("toggle_hotkey_name", name)
        return name, vk

    def apply_hotkey_setting(self):
        user32 = ctypes.windll.user32
        user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
        key_name, vk = self.get_hotkey_config()
        self.hotkey_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_TOGGLE, 0, vk))
        if hasattr(self, "tray_menu"):
            self.update_tray_menu()

    def on_hotkey_changed(self, index):
        key_name = self.hotkey_input.itemText(index)
        vk = self.hotkey_input.itemData(index)
        if not key_name or not isinstance(vk, int):
            return
        self.settings.setValue("toggle_hotkey_name", key_name)
        self.settings.setValue("toggle_hotkey_vk", vk)
        self.apply_hotkey_setting()

    def toggle_stretch_native_hotkey(self):
        dev = self.get_dev_name()
        if not dev: return
        current = resolution.get_current_resolution(dev)
        native = resolution.get_registry_resolution(dev)
        if not current or not native: return

        is_native_now = (
            current["width"] == native["width"] and
            current["height"] == native["height"] and
            current.get("hz") == native.get("hz")
        )

        if not is_native_now:
            self.last_stretch_modes[dev] = {
                "w": current["width"], "h": current["height"], "hz": current.get("hz")
            }
            self._save_last_stretch_modes()
            self.reset_res(enable_monitors=True)
            return

        target = self.last_stretch_modes.get(dev)
        if not target:
            themed_message_box(self, "Hotkey Toggle", "No previous stretch resolution found yet for this display.")
            return

        w, h, hz = int(target.get("w", 0)), int(target.get("h", 0)), target.get("hz")
        if w <= 0 or h <= 0:
            themed_message_box(self, "Hotkey Toggle", "Saved stretch resolution is invalid. Apply one once, then use the hotkey.")
            return
        if resolution.set_resolution(w, h, hz, dev):
            self.refresh_display()
        else:
            themed_message_box(self, "Hotkey Toggle", f"Failed to apply saved stretch resolution {w}x{h}.", QMessageBox.Icon.Warning)

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
        except: pass

    def show_update_notification(self, version):
        self.update_btn = QPushButton("! Update Available")
        self.update_btn.setFixedHeight(24)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet(f"QPushButton {{ background-color: {t.DESTRUCTIVE}; color: white; border-radius: 12px; font-weight: bold; font-size: 11px; padding: 0 12px; }} QPushButton:hover {{ background-color: {t.DESTRUCTIVE_HOVER}; }}")
        self.update_btn.clicked.connect(lambda: webbrowser.open("https://github.com/mohibk0004-del/easyres/releases/latest"))
        self.title_layout.insertWidget(self.title_layout.indexOf(self.settings_btn), self.update_btn)

    def closeEvent(self, event):
        if self.settings.value("minimize_to_tray", False, type=bool):
            event.ignore()
            self.hide()
        elif self.settings.value("dont_ask_tray_close", False, type=bool):
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
            self.tray_icon.hide()
            QApplication.instance().quit()
        else:
            reply, cb_checked = themed_message_box(
                self, "EasyRes", 
                "Do you want to minimize to the system tray instead of closing?", 
                QMessageBox.Icon.Question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                "Don't ask again"
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if cb_checked:
                    self.settings.setValue("minimize_to_tray", True)
                event.ignore()
                self.hide()
            elif reply == QMessageBox.StandardButton.No:
                if cb_checked:
                    self.settings.setValue("dont_ask_tray_close", True)
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
                self.tray_icon.hide()
                QApplication.instance().quit()
            else:
                event.ignore()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(t.SPACE_XL, t.SPACE_XL, t.SPACE_XL, t.SPACE_XL)
        
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setStyleSheet(styles.dialog_container_qss())
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(t.SHADOW_BLUR)
        shadow.setColor(QColor(t.SHADOW_COLOR))
        shadow.setOffset(0, t.SHADOW_OFFSET_Y)
        self.container.setGraphicsEffect(shadow)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setFixedHeight(t.TITLE_BAR_HEIGHT)
        title_bar.setStyleSheet(f"background-color: {t.BG_ELEVATED}; border-top-left-radius: {t.RADIUS_XL}px; border-top-right-radius: {t.RADIUS_XL}px; border-bottom: 1px solid {t.BORDER_SUBTLE};")
        self.title_layout = QHBoxLayout(title_bar)
        self.title_layout.setContentsMargins(t.SPACE_LG, 0, t.SPACE_SM, 0)
        
        logo = QLabel()
        logo.setFixedSize(18, 18)
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path_png = os.path.join(base_path, "icon.png")
        if os.path.exists(icon_path_png):
            logo.setPixmap(QPixmap(icon_path_png).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        title_label = QLabel("EasyRes")
        title_label.setStyleSheet(f"color: {t.TEXT_PRIMARY}; font-weight: bold; font-size: {t.FONT_MD}px; border: none; background: transparent;")
        
        self.settings_btn = IconButton("settings.svg", "Settings", "Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        
        help_btn = IconButton("help.svg", "Tutorial", "Help")
        help_btn.clicked.connect(self.show_tutorial)
        
        min_btn = IconButton("minimize.svg", "Minimize", "Minimize")
        min_btn.clicked.connect(self.showMinimized)
        
        self.max_btn = IconButton("maximize.svg", "Maximize", "Maximize")
        self.max_btn.clicked.connect(self.toggle_maximize)
        
        close_btn = IconButton("close.svg", "Close", "Close")
        close_btn.clicked.connect(self.close)
        
        self.title_layout.addWidget(logo)
        self.title_layout.addSpacing(t.SPACE_SM)
        self.title_layout.addWidget(title_label)
        self.title_layout.addStretch()
        self.title_layout.addWidget(self.settings_btn)
        self.title_layout.addWidget(help_btn)
        self.title_layout.addWidget(min_btn)
        self.title_layout.addWidget(self.max_btn)
        self.title_layout.addWidget(close_btn)
        
        title_bar.mousePressEvent = self.title_press
        title_bar.mouseMoveEvent = self.title_move
        title_bar.mouseDoubleClickEvent = self.title_double_click
        
        container_layout.addWidget(title_bar)
        
        body_scroll = QScrollArea()
        body_scroll.setWidgetResizable(True)
        body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body_scroll.setStyleSheet(styles.scrollbar_qss())
        
        body_widget = QWidget()
        body_widget.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(t.SPACE_XL, t.SPACE_XL, t.SPACE_XL, t.SPACE_XL)
        body_layout.setSpacing(t.SPACE_2XL)
        
        # Display selection
        mon_row = QHBoxLayout()
        mon_lbl = SectionLabel("DISPLAY")
        self.mon_combo = QComboBox()
        self.mon_combo.setStyleSheet(styles.combo_qss())
        for d in self.displays:
            clean_name = d['string'] if d['string'] else d['name']
            self.mon_combo.addItem(f"{clean_name} {'(Primary)' if d['primary'] else ''}", d['name'])
        self.mon_combo.currentIndexChanged.connect(self.on_monitor_changed)
        mon_row.addWidget(mon_lbl)
        mon_row.addSpacing(t.SPACE_MD)
        mon_row.addWidget(self.mon_combo, 1)
        body_layout.addLayout(mon_row)
        
        # Current Resolution Hero
        self.hero = ResolutionHero()
        body_layout.addWidget(self.hero)
        
        # Add Custom Res Form
        custom_res_header_layout = QHBoxLayout()
        lbl_custom_res = QLabel("ADD RESOLUTION")
        lbl_custom_res.setStyleSheet(f"color: {t.TEXT_PRIMARY}; font-size: {t.FONT_MD}px; font-weight: 700; margin-top: 12px;")
        self.lbl_experimental = QLabel("SAFE CATALOG")
        self.lbl_experimental.setStyleSheet(f"color: {t.ACCENT_PRIMARY}; font-size: {t.FONT_XS}px; font-weight: 700; background-color: {t.ACCENT_MUTED_BG}; border-radius: 7px; padding: 3px 7px; margin-top: 12px;")
        custom_res_header_layout.addWidget(lbl_custom_res)
        custom_res_header_layout.addWidget(self.lbl_experimental)
        custom_res_header_layout.addStretch()
        body_layout.addLayout(custom_res_header_layout)
        
        add_box = QWidget()
        add_box.setStyleSheet(f"background-color: {t.BG_ELEVATED}; border: 1px solid {t.BORDER_DEFAULT}; border-radius: {t.RADIUS_LG}px;")
        add_layout = QVBoxLayout(add_box)
        add_layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)
        add_layout.setSpacing(t.SPACE_MD)
        
        safe_row = QHBoxLayout()
        safe_lbl = SectionLabel("TESTED 1080P MODE")
        self.safe_res_combo = QComboBox()
        self.safe_res_combo.setStyleSheet(styles.combo_qss())
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
        self.inp_hz.setFixedWidth(84)
        self.inp_hz.addItem("Select Hz", None)
        
        btn_add = ActionButton("Add", primary=True)
        btn_add.setFixedWidth(60)
        btn_add.clicked.connect(self.add_custom_resolution)
        
        for inp in (self.inp_name, self.inp_rw, self.inp_rh):
            inp.setStyleSheet(styles.input_qss())
        self.inp_hz.setStyleSheet(styles.combo_qss())
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
        self.experimental_toggle.setStyleSheet(f"""
            QCheckBox {{ color: {t.TEXT_MUTED}; font-size: {t.FONT_MD}px; font-weight: 600; spacing: 8px; border: none; background: transparent; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t.BORDER_DEFAULT}; border-radius: 5px; background: {t.BG_CARD}; }}
            QCheckBox::indicator:checked {{ background: {t.ACCENT_PRIMARY}; border-color: {t.ACCENT_HOVER}; }}
        """)
        self.experimental_toggle.toggled.connect(self.set_experimental_mode)
        add_layout.addWidget(self.experimental_toggle)
        
        row2 = QHBoxLayout()
        lbl_pc = QLabel("Or add existing:")
        lbl_pc.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: {t.FONT_MD}px; border: none; background: transparent;")
        
        self.pc_res_combo = QComboBox()
        self.pc_res_combo.setStyleSheet(styles.combo_qss())
        
        self.pc_hz_combo = QComboBox()
        self.pc_hz_combo.setStyleSheet(styles.combo_qss())
        self.pc_hz_combo.setFixedWidth(84)
        
        self.pc_res_combo.currentIndexChanged.connect(self.on_pc_resolution_changed)
        
        btn_add_pc = ActionButton("Add")
        btn_add_pc.setFixedWidth(60)
        btn_add_pc.clicked.connect(self.add_pc_resolution)
        
        row2.addWidget(lbl_pc)
        row2.addWidget(self.pc_res_combo, 1)
        row2.addWidget(self.pc_hz_combo)
        row2.addWidget(btn_add_pc)
        add_layout.addLayout(row2)
        
        self.custom_safety_note = QLabel("Uses a tested 4:3 or 5:4 mode. Refresh rates come directly from your monitor's available modes.")
        self.custom_safety_note.setWordWrap(True)
        self.custom_safety_note.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: {t.FONT_SM}px; padding-top: 2px; border: none; background: transparent;")
        add_layout.addWidget(self.custom_safety_note)
        
        oled_warning = QLabel("Warning: Do not use stretch/monitor-toggle workflows on OLED panels.")
        oled_warning.setWordWrap(True)
        oled_warning.setStyleSheet(f"color: {t.ACCENT_PRIMARY}; font-size: {t.FONT_SM}px; border: none; background: transparent;")
        add_layout.addWidget(oled_warning)
        
        hotkey_row = QHBoxLayout()
        hotkey_lbl = SectionLabel("QUICK TOGGLE HOTKEY")
        self.hotkey_input = QComboBox()
        self.hotkey_input.setToolTip("Choose a function key from F1 to F12 for the global toggle.")
        self.hotkey_input.setFixedWidth(92)
        for function_key in range(1, 13):
            self.hotkey_input.addItem(f"F{function_key}", 0x6F + function_key)
        self.hotkey_input.setStyleSheet(styles.combo_qss())
        _current_name, current_vk = self.get_hotkey_config()
        self.hotkey_input.setCurrentIndex(current_vk - 0x70)
        self.hotkey_input.currentIndexChanged.connect(self.on_hotkey_changed)
        hotkey_row.addWidget(hotkey_lbl)
        hotkey_row.addStretch()
        hotkey_row.addWidget(self.hotkey_input)
        add_layout.addLayout(hotkey_row)
        
        hotkey_hint = QLabel("CS-style quick switch: toggles between your current stretch mode and native resolution with monitor enabled.")
        hotkey_hint.setWordWrap(True)
        hotkey_hint.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: {t.FONT_SM}px; border: none; background: transparent;")
        add_layout.addWidget(hotkey_hint)
        self.set_experimental_mode(False)
        self.on_safe_resolution_changed()
        
        body_layout.addWidget(add_box)
        
        lbl2 = SectionLabel("PRESETS & CUSTOM RESOLUTIONS")
        body_layout.addWidget(lbl2)
        
        self.presets_grid_widget = QWidget()
        self.presets_grid_widget.setStyleSheet("background: transparent;")
        self.presets_grid = QGridLayout(self.presets_grid_widget)
        self.presets_grid.setContentsMargins(0, 0, 0, 0)
        self.presets_grid.setSpacing(t.SPACE_SM)
        body_layout.addWidget(self.presets_grid_widget)
        
        lbl3 = SectionLabel("HARDWARE MONITORS")
        body_layout.addWidget(lbl3)
        
        self.hw_toggles = []
        hw_monitors = resolution.get_hardware_monitors()
        if not hw_monitors:
            no_hw = QLabel("No hardware monitors detected.")
            no_hw.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: {t.FONT_MD}px;")
            body_layout.addWidget(no_hw)
        else:
            self.hw_box = QWidget()
            self.hw_box.setStyleSheet(f"background-color: {t.BG_ELEVATED}; border-radius: {t.RADIUS_LG}px; border: 1px solid {t.BORDER_DEFAULT};")
            hw_layout = QVBoxLayout(self.hw_box)
            hw_layout.setContentsMargins(t.SPACE_LG, t.SPACE_MD, t.SPACE_LG, t.SPACE_MD)
            for hw in hw_monitors:
                row_layout = QHBoxLayout()
                lbl = QLabel(hw.get("Device Description", "Unknown Monitor"))
                lbl.setStyleSheet(f"color: {t.TEXT_PRIMARY}; font-size: {t.FONT_MD}px; font-weight: bold; border: none;")
                toggle = PremiumToggle()
                toggle.setChecked(hw.get("Status", "").lower() != "disabled", emit=False)
                def make_toggle_handler(instance_id, toggle_widget):
                    def handler():
                        en = toggle_widget.isChecked()
                        success = resolution.set_hardware_monitor_state(instance_id, en)
                        if not success:
                            themed_message_box(self, "Error", "Failed to change hardware state. Run as Admin?", QMessageBox.Icon.Warning)
                            toggle_widget.setChecked(not en, emit=False)
                        self._update_hw_box_style()
                    return handler
                toggle.toggled.connect(make_toggle_handler(hw.get("Instance ID", ""), toggle))
                row_layout.addWidget(lbl)
                row_layout.addStretch()
                row_layout.addWidget(toggle)
                hw_layout.addLayout(row_layout)
                self.hw_toggles.append((hw.get("Instance ID", ""), toggle))
            body_layout.addWidget(self.hw_box)
            self._update_hw_box_style()
            
        body_layout.addStretch()
        
        reset_layout = QHBoxLayout()
        reset_btn = ActionButton("Restore Native", destructive=True)
        reset_btn.setToolTip("Restore the saved native resolution without changing monitor power state")
        reset_btn.clicked.connect(lambda: self.reset_res(enable_monitors=False))
        reset_mon_btn = ActionButton("Restore + Enable Monitors", destructive=True)
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
        if os.path.exists(icon_path_png):
            self.tray_icon.setIcon(QIcon(icon_path_png))
        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet(styles.menu_qss())
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def _update_hw_box_style(self):
        if not hasattr(self, 'hw_box') or not self.hw_toggles: return
        any_disabled = any(not toggle.isChecked() for _, toggle in self.hw_toggles)
        if any_disabled:
            self.hw_box.setStyleSheet(f"background-color: {t.BG_ELEVATED}; border-radius: {t.RADIUS_LG}px; border: 1px solid {t.BORDER_DEFAULT}; border-left: 3px solid {t.ACCENT_PRIMARY};")
        else:
            self.hw_box.setStyleSheet(f"background-color: {t.BG_ELEVATED}; border-radius: {t.RADIUS_LG}px; border: 1px solid {t.BORDER_DEFAULT};")

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
            self.max_btn.set_svg("maximize.svg")
            self.max_btn.setToolTip("Maximize")
        else:
            self.showMaximized()
            self.max_btn.set_svg("restore.svg")
            self.max_btn.setToolTip("Restore")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if self.isMaximized():
                self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
                self.container.setStyleSheet(f"QWidget#Container {{ background-color: {t.BG_BASE}; border-radius: 0px; border: none; }}")
            else:
                self.centralWidget().layout().setContentsMargins(t.SPACE_XL, t.SPACE_XL, t.SPACE_XL, t.SPACE_XL)
                self.container.setStyleSheet(styles.dialog_container_qss())
            self.layout_presets_grid()

    def title_move(self, event):
        if self.offset is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.offset)
            event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'grip'):
            self.grip.move(self.width() - 20, self.height() - 20)
        self.layout_presets_grid()
        
    def layout_presets_grid(self):
        if not hasattr(self, 'presets_grid') or not hasattr(self, '_preset_cards'):
            return
        
        # calculate columns based on width
        available_width = self.width() - 80
        columns = max(2, min(4, available_width // (t.PRESET_CARD_WIDTH + 8)))
        
        # reposition items
        row = col = 0
        for i, card in enumerate(self._preset_cards):
            self.presets_grid.addWidget(card, row, col)
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def load_presets(self):
        dev_name = self.get_dev_name()
        presets_data = resolution.get_supported_resolutions(dev_name)
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

        if not presets_data:
            return

        while self.presets_grid.count():
            item = self.presets_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        hidden_presets = self.settings.value("hidden_presets", [])
        if isinstance(hidden_presets, str):
            hidden_presets = []
            
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
            
        self._preset_cards = []
        info = resolution.get_current_resolution(self.get_dev_name())
        curr_w = info['width'] if info else 0
        curr_h = info['height'] if info else 0
        curr_hz = info.get('hz') if info else None
        
        for idx, (w, h, ratio, label, is_custom, hz) in enumerate(final_presets):
            is_active = (w == curr_w and h == curr_h and (hz is None or hz == curr_hz))
            btn = PresetCard(w, h, ratio, label, is_custom, hz, is_active=is_active)
            btn.clicked.connect(lambda checked, width=w, height=h, freq=hz: self.change_res(width, height, freq))
            btn.delete_requested.connect(self.delete_custom_resolution)
            self._preset_cards.append(btn)
            btn.animate_entrance(delay_ms=idx * t.MOTION_STAGGER)
            
        self.layout_presets_grid()
                
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
        self.update_custom_hz_options()

    def set_experimental_mode(self, enabled):
        self.safe_res_combo.setEnabled(not enabled)
        self.inp_name.setEnabled(enabled)
        self.inp_rw.setEnabled(enabled)
        self.inp_rh.setEnabled(enabled)
        if not enabled:
            self.inp_name.setText("")
            self.inp_name.setPlaceholderText("Enable experimental to use")
        else:
            self.inp_name.setPlaceholderText("Custom Name")
        if enabled:
            self.lbl_experimental.setText("EXPERIMENTAL")
            self.lbl_experimental.setStyleSheet(f"color: {t.TEXT_PRIMARY}; font-size: {t.FONT_XS}px; font-weight: 700; background-color: {t.DESTRUCTIVE_MUTED_BG}; border-radius: 7px; padding: 3px 7px; margin-top: 12px;")
            self.custom_safety_note.setText("Highly unsupported and strongly discouraged. Use only if you understand EDID timing risks.")
        else:
            self.lbl_experimental.setText("SAFE CATALOG")
            self.lbl_experimental.setStyleSheet(f"color: {t.ACCENT_PRIMARY}; font-size: {t.FONT_XS}px; font-weight: 700; background-color: {t.ACCENT_MUTED_BG}; border-radius: 7px; padding: 3px 7px; margin-top: 12px;")
            self.custom_safety_note.setText("Uses a tested 4:3 or 5:4 mode. Refresh rates come directly from your monitor's available modes.")
            self.on_safe_resolution_changed()

    def update_custom_hz_options(self):
        if not hasattr(self, "inp_hz"): return
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
            themed_message_box(self, "Error", "Please fill all fields.", QMessageBox.Icon.Warning)
            return

        try:
            w_int, h_int = int(w), int(h)
        except ValueError:
            themed_message_box(self, "Invalid resolution", "Width and height must be numbers.", QMessageBox.Icon.Warning)
            return

        if w_int < 100 or h_int < 100:
            themed_message_box(self, "Unsupported size", "Custom modes must be at least 100×100.", QMessageBox.Icon.Warning)
            return
        if hz is None:
            themed_message_box(self, "Choose refresh rate", "Select a monitor refresh rate before adding this resolution.", QMessageBox.Icon.Warning)
            return

        aspect = resolution.get_aspect_ratio(w_int, h_int)
        safe_catalog = (w_int, h_int) in resolution.VALORANT_SAFE_RESOLUTIONS
        if not self.experimental_toggle.isChecked() and not safe_catalog:
            themed_message_box(self, "Experimental disabled", "Choose a listed 4:3 or 5:4 mode, or explicitly enable Experimental resolution.", QMessageBox.Icon.Warning)
            return
        if aspect in ("4:3", "5:4") and not safe_catalog:
            themed_message_box(self, "Unsupported 4:3 / 5:4 mode", "Choose one of EasyRes's tested 1080p catalog resolutions.", QMessageBox.Icon.Warning)
            return

        resolutions = self.settings.value("custom_resolutions", [])
        if not isinstance(resolutions, list):
            resolutions = []
        for r in resolutions:
            if r['name'] == name:
                themed_message_box(self, "Error", "A custom resolution with this name already exists.", QMessageBox.Icon.Warning)
                return
                
        warning = (f"{w_int}×{h_int} is outside the tested 4:3 / 5:4 VALORANT catalog.\n\n"
                   "This aspect ratio is highly unsupported, highly discouraged, and experimental. "
                   "It may fail in VALORANT, create black bars, or leave the display unusable until reset.\n\n"
                   "Continue anyway?") if aspect == "Experimental" else (
                   f"Adding {w_int}×{h_int} requires injecting it into your monitor's EDID configuration and restarting your graphics driver.\n\n"
                   "Your screen may flash black, and unsupported timings may fail.\n\nProceed to add and inject?")
        reply = themed_message_box(self, "Experimental resolution warning" if aspect == "Experimental" else "Safety Warning: Inject Resolution",
                                   warning, QMessageBox.Icon.Warning, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                    
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        dev_id = None
        for d in self.displays:
            if d['name'] == self.get_dev_name():
                dev_id = d.get('device_id')
                break
        
        active_ids = edid.get_active_monitor_device_ids()
        if not active_ids:
            themed_message_box(self, "Error", "Could not detect active monitor instances.", QMessageBox.Icon.Warning)
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
            themed_message_box(self, "Error", f"Failed to read EDID from the registry for target: {target_id}.", QMessageBox.Icon.Warning)
            return
            
        driver_restarted = False
        if not edid.is_resolution_injected(curr_edid, w_int, h_int, hz):
            new_edid = edid.inject_resolution(curr_edid, w_int, h_int, hz)
            if not new_edid:
                themed_message_box(self, "Error", "Failed to generate new EDID.", QMessageBox.Icon.Warning)
                return
                
            if edid.set_edid(target_id, new_edid):
                driver.restart_graphics_driver()
                driver_restarted = True
            else:
                themed_message_box(self, "Error", "Failed to write EDID override. Are you running as Admin?", QMessageBox.Icon.Warning)
                return
                
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
            reply = themed_message_box(self, "Delete Custom Resolution", 
                                       f"Are you sure you want to delete '{name}'?\nNote: This will remove it from the app but not un-inject it from the registry.",
                                       QMessageBox.Icon.Question, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
            reply, cb_checked = themed_message_box(
                self, "Apply Resolution", 
                f"Are you sure you want to apply {w}x{h}?\n\nIf your monitor does not support this resolution, the screen may go black for 15 seconds before reverting (or you might need to use the system tray to reset it).\n\nProceed?",
                QMessageBox.Icon.Question, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, "Don't ask me again"
            )
            
            if cb_checked:
                self.settings.setValue("ask_apply_res", False)
                
            if reply != QMessageBox.StandardButton.Yes:
                return
            
        if resolution.set_resolution(w, h, hz, self.get_dev_name()):
            dev = self.get_dev_name()
            native = resolution.get_registry_resolution(dev)
            if native and (w != native["width"] or h != native["height"] or hz != native.get("hz")):
                self.last_stretch_modes[dev] = {"w": w, "h": h, "hz": hz}
                self._save_last_stretch_modes()
            self.refresh_display()
            self.load_presets()
        else:
            themed_message_box(self, "Error", f"Failed to set custom resolution {w}x{h}. The graphics driver might not support it.", QMessageBox.Icon.Warning)

    def reset_res(self, enable_monitors=False):
        if enable_monitors:
            for inst_id, toggle in getattr(self, 'hw_toggles', []):
                toggle.setChecked(True, emit=False)
                resolution.set_hardware_monitor_state(inst_id, True)
            self._update_hw_box_style()
            resolution.set_monitor_state(self.get_dev_name(), True)
            
        if resolution.reset_resolution(self.get_dev_name()):
            self.refresh_display()
            self.load_presets()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

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
            self.hero.set_resolution(info['width'], info['height'], info['hz'])
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

        hotkey_name, _ = self.get_hotkey_config()
        hotkey_action = self.tray_menu.addAction(f"Toggle Stretch <-> Native ({hotkey_name})")
        hotkey_action.triggered.connect(self.toggle_stretch_native_hotkey)
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
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
            self.tray_icon.hide()
            QApplication.instance().quit()
        quit_action.triggered.connect(quit_app)

    def populate_pc_resolutions(self):
        if not hasattr(self, 'pc_res_combo'): return
        self.pc_res_combo.blockSignals(True)
        self.pc_res_combo.clear()
        dev = self.get_dev_name()
        if not dev: return
        modes = resolution.get_all_resolutions(dev)
        unique_res = []
        for w, h, hz in modes:
            if (w, h) not in unique_res:
                unique_res.append((w, h))
        for w, h in unique_res:
            self.pc_res_combo.addItem(f"{w} × {h}", (w, h))
        self.pc_res_combo.blockSignals(False)
        self.on_pc_resolution_changed()

    def on_pc_resolution_changed(self):
        if not hasattr(self, 'pc_hz_combo'): return
        self.pc_hz_combo.clear()
        data = self.pc_res_combo.currentData()
        if not data: return
        w, h = data
        dev = self.get_dev_name()
        if not dev: return
        rates = resolution.get_monitor_refresh_rates(w, h, dev)
        for hz in rates:
            self.pc_hz_combo.addItem(f"{hz} Hz", hz)

    def add_pc_resolution(self):
        res_data = self.pc_res_combo.currentData()
        hz = self.pc_hz_combo.currentData()
        if not res_data or not hz: return
        w, h = res_data
        name = f"{w}x{h}@{hz}Hz (PC)"
        resolutions = self.settings.value("custom_resolutions", [])
        if not isinstance(resolutions, list):
            resolutions = []
        for r in resolutions:
            if r['w'] == w and r['h'] == h and r.get('hz') == hz:
                themed_message_box(self, "Error", "This resolution is already in presets.", QMessageBox.Icon.Warning)
                return
                
        resolutions.append({'name': name, 'w': w, 'h': h, 'hz': hz})
        self.settings.setValue("custom_resolutions", resolutions)
        self.load_presets()
