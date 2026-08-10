import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect, QGridLayout,
                             QComboBox, QLineEdit, QSizePolicy, QMessageBox, QSizeGrip, QSystemTrayIcon, QMenu)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize, pyqtProperty
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QIntValidator, QBrush, QIcon, QPixmap

import resolution

class AppleToggle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = True
        self._pos = 22 # handle position (2 to 22)
        
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
        # Override to catch toggles
        pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        bg_color = QColor("#34c759") if self._checked else QColor("rgba(255,255,255,0.1)")
        
        # When animating, we can crossfade color, but simple solid works because handle covers it
        if self.anim.state() == QPropertyAnimation.State.Running:
            if not self._checked: 
                bg_color = QColor("rgba(255,255,255,0.1)")
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 13, 13)
        p.fillPath(path, QBrush(bg_color))
        
        # Draw handle
        handle_rect = QRect(self._pos, 2, 22, 22)
        p.setBrush(QBrush(QColor("white")))
        p.setPen(Qt.PenStyle.NoPen)
        
        # Small shadow for handle
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
                background-color: transparent;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                color: #86868b;
                font-size: 13px;
                font-weight: 500;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #1c1c1e;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QPushButton:pressed {
                background-color: #122a47;
                padding: 12px 8px 8px 12px;
            }
        """)

class PresetCard(QPushButton):
    def __init__(self, width, height, ratio, label, parent=None):
        super().__init__(parent)
        self.res_width = width
        self.res_height = height
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(124, 76)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(2)
        
        res_label = QLabel(f"{width} × {height}")
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
        
        self.setStyleSheet("""
            PresetCard {
                background-color: #1c1c1e;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
            PresetCard:hover {
                background-color: #242426;
            }
            PresetCard:pressed {
                background-color: #122a47;
            }
        """)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(480, 980)
        self.setMinimumSize(320, 600)
        self.offset = None
        self.displays = resolution.get_displays()
        self.current_display = self.displays[0] if self.displays else None
        
        self.init_ui()
        self.refresh_display()
        
        # Entrance Animation
        self.setWindowOpacity(0.0)
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(500)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.opacity_anim.start()
        
        # System Tray Icon
        self.tray_icon = QSystemTrayIcon(self)
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#ff9f0a")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 16, 16, 4, 4)
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(tray_menu)
        
        def tray_activated(reason):
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self.showNormal()
                
        self.tray_icon.activated.connect(tray_activated)
        self.tray_icon.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Main Layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Container for background and shadow
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setStyleSheet("""
            QWidget#Container {
                background-color: #0d0d0d;
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.15);
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
        
        # Title Bar
        title_bar = QWidget()
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet("background-color: rgba(28, 28, 30, 0.9); border-top-left-radius: 16px; border-top-right-radius: 16px; border-bottom: 1px solid rgba(255,255,255,0.1);")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        
        # Logo placeholder
        logo = QLabel("E")
        logo.setFixedSize(18, 18)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background-color: #ff9f0a; color: white; border-radius: 4px; font-weight: bold; font-size: 11px;")
        
        title_label = QLabel("EasyRes")
        title_label.setStyleSheet("color: #86868b; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        
        min_btn = QPushButton("—")
        min_btn.setFixedSize(28, 28)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setStyleSheet("QPushButton { color: #86868b; background: transparent; border: none; font-size: 12px; font-weight: bold;} QPushButton:hover { color: white; }")
        min_btn.clicked.connect(self.showMinimized)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { color: #86868b; background: transparent; border: none; font-size: 14px; } QPushButton:hover { color: white; }")
        close_btn.clicked.connect(self.close)
        
        title_layout.addWidget(logo)
        title_layout.addSpacing(10)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(min_btn)
        title_layout.addWidget(close_btn)
        
        # Custom Title Bar Dragging
        title_bar.mousePressEvent = self.title_press
        title_bar.mouseMoveEvent = self.title_move
        
        container_layout.addWidget(title_bar)
        
        # Content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Target Monitor Selector
        mon_row = QHBoxLayout()
        mon_lbl = QLabel("DISPLAY")
        mon_lbl.setStyleSheet("color: #86868b; font-size: 11px; font-weight: bold;")
        
        self.mon_combo = QComboBox()
        self.mon_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: white;
                padding: 4px 8px;
            }
            QComboBox::drop-down { border: none; }
        """)
        for d in self.displays:
            clean_name = d['string'] if d['string'] else d['name']
            idx = self.mon_combo.count()
            self.mon_combo.addItem(f"{clean_name} {'(Primary)' if d['primary'] else ''}", d['name'])
        
        self.mon_combo.currentIndexChanged.connect(self.on_monitor_changed)
        
        mon_row.addWidget(mon_lbl)
        mon_row.addSpacing(10)
        mon_row.addWidget(self.mon_combo, 1)
        content_layout.addLayout(mon_row)
        
        content_layout.addSpacing(10)
        
        # Current Display
        curr_box = QWidget()
        curr_box.setStyleSheet("background-color: #1c1c1e; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.1);")
        curr_layout = QVBoxLayout(curr_box)
        curr_layout.setContentsMargins(20, 20, 20, 20)
        
        lbl1 = QLabel("CURRENT RESOLUTION")
        lbl1.setStyleSheet("color: #86868b; font-size: 11px; font-weight: bold; letter-spacing: 2px;")
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.curr_res = QLabel("1920 × 1080")
        self.curr_res.setStyleSheet("color: #f5f5f7; font-size: 32px; font-weight: bold;")
        self.curr_res.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.curr_hz = QLabel("144 Hz")
        self.curr_hz.setStyleSheet("color: #ff9f0a; font-size: 15px; font-weight: bold;")
        self.curr_hz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        curr_layout.addWidget(lbl1)
        curr_layout.addWidget(self.curr_res)
        curr_layout.addWidget(self.curr_hz)
        
        content_layout.addWidget(curr_box)
        
        # Custom Resolution Header
        content_layout.addSpacing(10)
        custom_header = QHBoxLayout()
        custom_header.setContentsMargins(0, 10, 0, 0)
        
        custom_lbl = QLabel("CUSTOM")
        custom_lbl.setStyleSheet("color: #86868b; font-size: 11px; font-weight: bold;")
        
        exp_lbl = QLabel("EXPERIMENTAL")
        exp_lbl.setStyleSheet("background-color: rgba(255, 159, 10, 0.2); color: #ff9f0a; font-size: 9px; font-weight: bold; padding: 2px 6px; border-radius: 4px;")
        
        custom_header.addWidget(custom_lbl)
        custom_header.addWidget(exp_lbl)
        custom_header.addStretch()
        content_layout.addLayout(custom_header)
        
        custom_row = QHBoxLayout()
        self.inp_w = QLineEdit()
        self.inp_w.setPlaceholderText("Width")
        self.inp_w.setValidator(QIntValidator(100, 10000))
        
        cross = QLabel("×")
        cross.setStyleSheet("color: #86868b;")
        
        self.inp_h = QLineEdit()
        self.inp_h.setPlaceholderText("Height")
        self.inp_h.setValidator(QIntValidator(100, 10000))
        
        for inp in (self.inp_w, self.inp_h):
            inp.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    color: white;
                    padding: 8px;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #ff9f0a;
                    background-color: rgba(255, 255, 255, 0.1);
                }
            """)
            
        btn_apply_custom = ActionButton("Apply")
        btn_apply_custom.clicked.connect(self.apply_custom_res)
        
        custom_row.addWidget(self.inp_w)
        custom_row.addWidget(cross)
        custom_row.addWidget(self.inp_h)
        custom_row.addWidget(btn_apply_custom)
        content_layout.addLayout(custom_row)
        
        # Presets Label
        lbl2 = QLabel("PRESETS")
        lbl2.setStyleSheet("color: #86868b; font-size: 11px; font-weight: bold; margin-top: 20px;")
        content_layout.addWidget(lbl2)
        
        # Presets Grid
        grid = QGridLayout()
        grid.setSpacing(8)
        
        presets_data = [
            (1920, 1080, "16:9", "Native"),
            (1680, 1050, "16:10", "Slight Stretch"),
            (1600, 900, "16:9", "Compact"),
            (1440, 1080, "4:3", "Popular"),
            (1280, 1024, "5:4", "CS Classic"),
            (1280, 960, "4:3", "Classic")
        ]
        
        row, col = 0, 0
        for w, h, r, l in presets_data:
            btn = PresetCard(w, h, r, l)
            btn.clicked.connect(lambda checked, width=w, height=h: self.change_res(width, height))
            grid.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
                
        content_layout.addLayout(grid)
        
        # Hardware Monitors Label
        lbl3 = QLabel("HARDWARE MONITORS")
        lbl3.setStyleSheet("color: #86868b; font-size: 11px; font-weight: bold; margin-top: 20px;")
        content_layout.addWidget(lbl3)
        
        hw_monitors = resolution.get_hardware_monitors()
        if not hw_monitors:
            no_hw = QLabel("No hardware monitors detected.")
            no_hw.setStyleSheet("color: #86868b; font-size: 12px; margin-top: 10px;")
            content_layout.addWidget(no_hw)
        else:
            hw_box = QWidget()
            hw_box.setStyleSheet("background-color: #1c1c1e; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1);")
            hw_layout = QVBoxLayout(hw_box)
            hw_layout.setContentsMargins(15, 10, 15, 10)
            
            for hw in hw_monitors:
                row = QHBoxLayout()
                lbl = QLabel(hw.get("Device Description", "Unknown Monitor"))
                lbl.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
                
                toggle = AppleToggle()
                # Status: "Disabled" or something else
                toggle.setChecked(hw.get("Status", "").lower() != "disabled")
                
                # Capture variable safely in lambda
                def make_toggle_handler(instance_id, toggle_widget):
                    def handler():
                        en = toggle_widget.isChecked()
                        success = resolution.set_hardware_monitor_state(instance_id, en)
                        if not success:
                            QMessageBox.warning(self, "Error", "Failed to change hardware state. Did you run as Administrator?")
                            toggle_widget.setChecked(not en)
                    return handler
                    
                toggle.toggled = make_toggle_handler(hw.get("Instance ID", ""), toggle)
                
                row.addWidget(lbl)
                row.addStretch()
                row.addWidget(toggle)
                hw_layout.addLayout(row)
                
            content_layout.addWidget(hw_box)
            
        content_layout.addStretch()
        
        # Reset Button
        reset_btn = ActionButton("Reset to Native")
        reset_btn.clicked.connect(self.reset_res)
        content_layout.addWidget(reset_btn)
        
        container_layout.addWidget(content)
        main_layout.addWidget(self.container)
        
        # Overlay QSizeGrip for reliable resizing
        self.grip = QSizeGrip(self)
        self.grip.resize(20, 20)
        
        # System Tray Menu
        self.tray_icon = QSystemTrayIcon(self)
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor("#ff9f0a")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(4, 4, 24, 24, 6, 6)
        p.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        
        self.tray_menu = QMenu()
        show_action = self.tray_menu.addAction("Show EasyRes")
        show_action.triggered.connect(self.showNormal)
        self.tray_menu.addSeparator()
        
        presets_menu = self.tray_menu.addMenu("Quick Switch")
        native_act = presets_menu.addAction("Native (Reset)")
        native_act.triggered.connect(self.reset_res)
        presets_menu.addSeparator()
        
        for w, h, r, l in presets_data:
            act = presets_menu.addAction(f"{w}x{h} ({l})")
            act.triggered.connect(lambda checked, width=w, height=h: self.change_res(width, height))
            
        self.tray_menu.addSeparator()
        quit_action = self.tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        
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

    def get_dev_name(self):
        return self.current_display['name'] if self.current_display else None

    def refresh_display(self):
        info = resolution.get_current_resolution(self.get_dev_name())
        if info:
            self.curr_res.setText(f"{info['width']} × {info['height']}")
            self.curr_hz.setText(f"{info['hz']} Hz")
        else:
            self.curr_res.setText("Disabled")
            self.curr_hz.setText("N/A")

    def change_res(self, w, h):
        if resolution.set_resolution(w, h, self.get_dev_name()):
            self.refresh_display()
        else:
            QMessageBox.warning(self, "Error", f"Failed to set custom resolution {w}x{h}. The graphics driver might not support it, or you may need to add it via NVIDIA Control Panel/CRU first.")

    def apply_custom_res(self):
        try:
            w = int(self.inp_w.text())
            h = int(self.inp_h.text())
            self.change_res(w, h)
        except ValueError:
            pass

    def reset_res(self):
        if resolution.reset_resolution(self.get_dev_name()):
            self.refresh_display()

    def title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.offset = event.globalPosition().toPoint() - self.pos()

    def title_move(self, event):
        if self.offset is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.offset)

    # def nativeEvent(self, eventType, message):
    #     if eventType == b"windows_generic_MSG":
    #         import ctypes
    #         from ctypes.wintypes import MSG
    #         msg = MSG.from_address(message.__int__())
    #         if msg.message == 0x0084: # WM_NCHITTEST
    #             x = msg.lParam & 0xffff
    #             y = (msg.lParam >> 16) & 0xffff
    #             if x > 32767: x -= 65536
    #             if y > 32767: y -= 65536
    #             
    #             pos = self.mapFromGlobal(QPoint(x, y))
    #             w = self.width()
    #             h = self.height()
    #             
    #             margin = 10
    #             left = pos.x() < margin
    #             right = pos.x() > w - margin
    #             top = pos.y() < margin
    #             bottom = pos.y() > h - margin
    #             
    #             if top and left: return True, 13 # HTTOPLEFT
    #             if top and right: return True, 14 # HTTOPRIGHT
    #             if bottom and left: return True, 16 # HTBOTTOMLEFT
    #             if bottom and right: return True, 17 # HTBOTTOMRIGHT
    #             if left: return True, 10 # HTLEFT
    #             if right: return True, 11 # HTRIGHT
    #             if top: return True, 12 # HTTOP
    #             if bottom: return True, 15 # HTBOTTOM
    #             
    #     return super().nativeEvent(eventType, message)
