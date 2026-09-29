import os
import ctypes
import threading
from ctypes import wintypes

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect,
    QGridLayout, QComboBox, QLineEdit, QSystemTrayIcon, QMenu, QScrollArea, QMessageBox,
    QCheckBox, QPushButton, QLabel,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QSettings, QTimer, pyqtSignal, QAbstractNativeEventFilter,
)
from PyQt6.QtGui import QColor, QIntValidator, QIcon, QPixmap, QKeySequence, QShortcut

from theme import tokens as t
from theme import styles
from theme.assets import asset_base_path
from theme.motion import duration
from ui.widgets import (
    PremiumToggle, ActionButton, IconButton, SectionLabel, StatPill, ModeRow, Panel, make_label, set_tone,
)
from ui.dialogs import SettingsDialog, TutorialDialog, RevertDialog, themed_message_box
from ui.workers import run_async
import resolution
import edid
import driver
import updater

StandardButton = QMessageBox.StandardButton

WM_HOTKEY = 0x0312
HOTKEY_ID_TOGGLE = 1
HOTKEY_ID_RESTORE = 2
DEFAULT_HOTKEY_VK = 0x75  # F6
VK_F1 = 0x70
VK_F12 = 0x7B
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
RESTORE_HOTKEY_MODS = MOD_CONTROL | MOD_SHIFT
RESTORE_HOTKEY_VK = VK_F12
RESTORE_HOTKEY_TEXT = "Ctrl+Shift+F12"
HOTKEY_MODIFIERS = (
    ("No modifier", 0),
    ("Ctrl", MOD_CONTROL),
    ("Alt", MOD_ALT),
    ("Shift", MOD_SHIFT),
    ("Ctrl+Shift", MOD_CONTROL | MOD_SHIFT),
    ("Ctrl+Alt", MOD_CONTROL | MOD_ALT),
)

ASPECT_ORDER = ("My Modes", "16:9", "16:10", "21:9", "4:3", "5:4", "Other")
RESIZE_MARGIN = 6


class HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, callbacks):
        super().__init__()
        self.callbacks = callbacks

    def nativeEventFilter(self, eventType, message):
        event_type = eventType.encode() if isinstance(eventType, str) else bytes(eventType)
        if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam in self.callbacks:
            self.callbacks[msg.wParam]()
            return True, 0
        return False, 0


class TitleBar(QWidget):
    """Drag area. Uses the native move so Windows Snap works."""

    def __init__(self, window):
        super().__init__()
        self._window = window
        self._offset = None
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        handle = self._window.windowHandle()
        if handle is not None and handle.startSystemMove():
            event.accept()
            return
        self._offset = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event):
        if self._offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self._window.isMaximized():
                return
            self._window.move(event.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, event):
        self._offset = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_maximize()


class ResizeHandle(QWidget):
    def __init__(self, parent, edges, cursor):
        super().__init__(parent)
        self.edges = edges
        self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemResize(self.edges)
            event.accept()


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class MainWindow(QMainWindow):
    update_progress = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EasyRes")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
        self._fit_initial_size()

        app = QApplication.instance()
        if not isinstance(app.style(), styles.AppStyle):
            app.setStyle(styles.AppStyle())
        app.setStyleSheet(styles.app_qss())

        self.settings = QSettings("EasyRes", "App")
        self.displays = resolution.get_displays()
        self.current_display = next((d for d in self.displays if d.get("primary")), None) or (
            self.displays[0] if self.displays else None
        )
        self._preset_cache = {}
        self._preset_retry_pending = set()
        self._rates_by_mode = {}
        self._tiles = []
        self._group_labels = {}
        self._columns = 0
        self._busy = False
        self._revert_dialog = None
        self._quitting = False
        self._update_in_progress = False
        self.available_release = None
        self.hw_monitors = []
        self.hw_toggles = []
        self.hotkey_registered = False
        self.restore_hotkey_registered = False
        self.last_stretch_modes = self._load_last_stretch_modes()

        self.init_ui()
        self.init_hotkeys()
        self.refresh_display()
        self.load_presets()
        self.refresh_hardware_monitors()

        QTimer.singleShot(400, self.check_first_run)
        self.update_progress.connect(self.on_update_progress)
        run_async(updater.fetch_latest_release, on_done=self._on_background_release, on_error=lambda _msg: None)

        ms = duration(t.MOTION_FADE)
        if ms:
            self.setWindowOpacity(0.0)
            self.opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
            self.opacity_anim.setDuration(ms)
            self.opacity_anim.setStartValue(0.0)
            self.opacity_anim.setEndValue(1.0)
            self.opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            QTimer.singleShot(0, self.opacity_anim.start)

    # ------------------------------------------------------------------
    # Settings helpers (values come from the user-writable registry, so
    # validate every field before use).
    # ------------------------------------------------------------------
    def _load_customs(self):
        raw = self.settings.value("custom_resolutions", [])
        if not isinstance(raw, list):
            return []
        customs = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            w, h = _as_int(item.get("w")), _as_int(item.get("h"))
            name = item.get("name")
            hz = item.get("hz")
            hz = _as_int(hz) if hz is not None else None
            if not w or not h or w <= 0 or h <= 0 or not isinstance(name, str) or not name.strip():
                continue
            customs.append({"name": name.strip()[:64], "w": w, "h": h, "hz": hz})
        return customs

    def _save_customs(self, customs):
        self.settings.setValue("custom_resolutions", customs)

    def _load_hidden(self):
        raw = self.settings.value("hidden_presets", [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, str)]

    def _load_hotkey_target(self):
        raw = self.settings.value("hotkey_target_res", None)
        if not isinstance(raw, dict):
            return None
        w, h = _as_int(raw.get("w")), _as_int(raw.get("h"))
        hz = _as_int(raw.get("hz")) if raw.get("hz") is not None else None
        if not w or not h or w <= 0 or h <= 0:
            return None
        return {"w": w, "h": h, "hz": hz}

    def _load_last_stretch_modes(self):
        raw = self.settings.value("last_stretch_modes", {})
        return raw if isinstance(raw, dict) else {}

    def _save_last_stretch_modes(self):
        self.settings.setValue("last_stretch_modes", self.last_stretch_modes)

    def _edid_backups(self):
        raw = self.settings.value("edid_backups", {})
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}

    def has_edid_backup(self):
        return bool(self._edid_backups())

    # ------------------------------------------------------------------
    # Window chrome
    # ------------------------------------------------------------------
    def _fit_initial_size(self):
        screen = QApplication.primaryScreen()
        width, height = 1120, 760
        if screen:
            available = screen.availableGeometry()
            width = max(t.WINDOW_MIN_WIDTH, min(width, available.width() - 80))
            height = max(t.WINDOW_MIN_HEIGHT, min(height, available.height() - 60))
        self.resize(width, height)

    def adjust_window_size(self):
        screen = self.screen() or QApplication.primaryScreen()
        if not screen or self.isMaximized():
            return
        rect = screen.availableGeometry()
        w = min(self.width(), max(self.minimumWidth(), rect.width()))
        h = min(self.height(), max(self.minimumHeight(), rect.height()))
        if (w, h) != (self.width(), self.height()):
            self.resize(w, h)
            geometry = self.frameGeometry()
            geometry.moveCenter(rect.center())
            self.move(geometry.topLeft())

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange and hasattr(self, "container"):
            maximized = self.isMaximized()
            margin = 0 if maximized else t.SPACE_LG
            self.centralWidget().layout().setContentsMargins(margin, margin, margin, margin)
            styles.set_props(self.container, maximized=maximized)
            for widget in self.container.findChildren(QWidget, "TitleBar") + self.container.findChildren(QWidget, "ActionBar"):
                styles.repolish(widget)
            self.max_btn.set_icon_name("restore" if maximized else "maximize")
            self.max_btn.setToolTip("Restore" if maximized else "Maximize")
            self.max_btn.setAccessibleName(self.max_btn.toolTip())
            for handle in self._resize_handles:
                handle.setVisible(not maximized)
            self._position_resize_handles()

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_shown_once", False):
            self._shown_once = True
            # No control starts with a focus ring; Tab enters the controls.
            self.container.setFocus(Qt.FocusReason.OtherFocusReason)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_handles()

    def eventFilter(self, obj, event):
        if (hasattr(self, "mode_scroll") and obj is self.mode_scroll.viewport()
                and event.type() == event.Type.Resize):
            self._relayout_if_columns_changed()
        return super().eventFilter(obj, event)

    def _position_resize_handles(self):
        if not hasattr(self, "_resize_handles"):
            return
        rect = self.container.geometry()
        m = RESIZE_MARGIN
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        geometry = {
            "left": (x, y + m, m, h - 2 * m),
            "right": (x + w - m, y + m, m, h - 2 * m),
            "top": (x + m, y, w - 2 * m, m),
            "bottom": (x + m, y + h - m, w - 2 * m, m),
            "tl": (x, y, m, m),
            "tr": (x + w - m, y, m, m),
            "bl": (x, y + h - m, m, m),
            "br": (x + w - m, y + h - m, m, m),
        }
        for handle in self._resize_handles:
            handle.setGeometry(*geometry[handle.objectName()])
            handle.raise_()

    def _build_resize_handles(self, parent):
        E = Qt.Edge
        C = Qt.CursorShape
        specs = (
            ("left", E.LeftEdge, C.SizeHorCursor),
            ("right", E.RightEdge, C.SizeHorCursor),
            ("top", E.TopEdge, C.SizeVerCursor),
            ("bottom", E.BottomEdge, C.SizeVerCursor),
            ("tl", E.TopEdge | E.LeftEdge, C.SizeFDiagCursor),
            ("br", E.BottomEdge | E.RightEdge, C.SizeFDiagCursor),
            ("tr", E.TopEdge | E.RightEdge, C.SizeBDiagCursor),
            ("bl", E.BottomEdge | E.LeftEdge, C.SizeBDiagCursor),
        )
        self._resize_handles = []
        for name, edges, cursor in specs:
            handle = ResizeHandle(parent, edges, cursor)
            handle.setObjectName(name)
            self._resize_handles.append(handle)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)

        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.container.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(t.SHADOW_BLUR)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, t.SHADOW_OFFSET_Y)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self._build_title_bar())

        body_scroll = QScrollArea()
        body_scroll.setWidgetResizable(True)
        body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)
        body_layout.setSpacing(t.SPACE_LG)

        body_layout.addLayout(self._build_display_row())
        body_layout.addWidget(self._build_status_band())

        workspace_row = QHBoxLayout()
        workspace_row.setSpacing(t.SPACE_LG)
        workspace_row.addWidget(self._build_browser_panel(), 6)
        side_widget = QWidget()
        side_widget.setMinimumWidth(300)
        side_widget.setMaximumWidth(440)
        side_panel = QVBoxLayout(side_widget)
        side_panel.setContentsMargins(0, 0, 0, 0)
        side_panel.setSpacing(t.SPACE_LG)
        side_panel.addWidget(self._build_quick_toggle_panel())
        side_panel.addWidget(self._build_custom_panel())
        side_panel.addWidget(self._build_hardware_panel())
        side_panel.addStretch()
        workspace_row.addWidget(side_widget, 4)
        body_layout.addLayout(workspace_row, 1)

        body_scroll.setWidget(body_widget)
        container_layout.addWidget(body_scroll, 1)
        container_layout.addWidget(self._build_action_bar())

        main_layout.addWidget(self.container)
        self._build_resize_handles(central_widget)

        restore_shortcut = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        restore_shortcut.activated.connect(lambda: self.reset_res(enable_monitors=False))
        filter_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        filter_shortcut.activated.connect(lambda: self.mode_filter.setFocus())

        self._build_tray()
        self._sync_hotkey_labels()

    def _build_title_bar(self):
        title_bar = TitleBar(self)
        title_bar.setFixedHeight(48)
        self.title_layout = QHBoxLayout(title_bar)
        self.title_layout.setContentsMargins(t.SPACE_LG, 0, t.SPACE_SM, 0)
        self.title_layout.setSpacing(t.SPACE_XS)

        logo = QLabel()
        logo.setFixedSize(18, 18)
        icon_file = os.path.join(asset_base_path(), "icon.png")
        if os.path.exists(icon_file):
            scale = 3
            pixmap = QPixmap(icon_file).scaled(18 * scale, 18 * scale, Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(scale)
            logo.setPixmap(pixmap)
        logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        title_label = make_label("EasyRes", role="app-title")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.update_btn = QPushButton()
        self.update_btn.setProperty("variant", "pill")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.update_btn.setToolTip("Download, verify, and install the update, then restart EasyRes")
        self.update_btn.clicked.connect(self.prompt_update)
        self.update_btn.hide()

        self.settings_btn = IconButton("settings", "Settings", "Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        help_btn = IconButton("help", "Getting started", "Getting started")
        help_btn.clicked.connect(self.show_tutorial)
        min_btn = IconButton("minimize", "Minimize", "Minimize")
        min_btn.clicked.connect(self.showMinimized)
        self.max_btn = IconButton("maximize", "Maximize", "Maximize")
        self.max_btn.clicked.connect(self.toggle_maximize)
        close_btn = IconButton("close", "Close", "Close", danger=True)
        close_btn.clicked.connect(self.close)

        self.title_layout.addWidget(logo)
        self.title_layout.addSpacing(t.SPACE_SM)
        self.title_layout.addWidget(title_label)
        self.title_layout.addStretch()
        self.title_layout.addWidget(self.update_btn)
        self.title_layout.addSpacing(t.SPACE_SM)
        for button in (self.settings_btn, help_btn, min_btn, self.max_btn, close_btn):
            self.title_layout.addWidget(button)
        return title_bar

    def _build_display_row(self):
        row = QHBoxLayout()
        row.setSpacing(t.SPACE_MD)
        label = SectionLabel("Display")
        self.mon_combo = QComboBox()
        self.mon_combo.setAccessibleName("Display")
        label.setBuddy(self.mon_combo)
        for d in self.displays:
            clean_name = d.get("string") or d.get("name")
            primary = "  ·  Primary" if d.get("primary") else ""
            self.mon_combo.addItem(f"{clean_name}{primary}", d.get("name"))
        if self.current_display:
            index = self.mon_combo.findData(self.current_display.get("name"))
            if index >= 0:
                self.mon_combo.setCurrentIndex(index)
        self.mon_combo.currentIndexChanged.connect(self.on_monitor_changed)
        row.addWidget(label)
        row.addWidget(self.mon_combo, 1)
        return row

    def _build_status_band(self):
        band = QWidget()
        layout = QHBoxLayout(band)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_MD)
        self.stat_resolution = StatPill("Current", "--")
        self.stat_refresh = StatPill("Refresh", "--")
        self.stat_mode = StatPill("Mode", "--")
        self.stat_monitor = StatPill("Monitors", "--")
        layout.addWidget(self.stat_resolution, 2)
        layout.addWidget(self.stat_refresh, 1)
        layout.addWidget(self.stat_mode, 1)
        layout.addWidget(self.stat_monitor, 1)
        return band

    def _build_browser_panel(self):
        panel = Panel()
        panel.setMinimumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)
        layout.setSpacing(t.SPACE_MD)

        header = QHBoxLayout()
        header.addWidget(SectionLabel("Resolutions"))
        header.addStretch()
        self.mode_count_label = make_label("", role="caption")
        header.addWidget(self.mode_count_label)
        layout.addLayout(header)

        self.mode_filter = QLineEdit()
        self.mode_filter.setPlaceholderText("Filter  (e.g. 1440, 4:3, 144)")
        self.mode_filter.setAccessibleName("Filter resolutions")
        self.mode_filter.setClearButtonEnabled(True)
        self.mode_filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.mode_filter)

        self.mode_scroll = QScrollArea()
        self.mode_scroll.setWidgetResizable(True)
        self.mode_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mode_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.mode_scroll.setMinimumHeight(200)
        self.presets_grid_widget = QWidget()
        self.presets_grid = QGridLayout(self.presets_grid_widget)
        self.presets_grid.setContentsMargins(0, 0, 4, 0)
        self.presets_grid.setHorizontalSpacing(t.SPACE_SM)
        self.presets_grid.setVerticalSpacing(t.SPACE_SM)
        self.mode_scroll.setWidget(self.presets_grid_widget)
        self.mode_scroll.viewport().installEventFilter(self)
        layout.addWidget(self.mode_scroll, 1)

        hint = make_label("Click to apply. Right-click for refresh rates, saving, or hiding.", role="caption", wrap=True)
        layout.addWidget(hint)
        return panel

    def _build_quick_toggle_panel(self):
        panel = Panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)
        layout.setSpacing(t.SPACE_MD)

        header = QHBoxLayout()
        header.addWidget(SectionLabel("Quick Toggle"))
        header.addStretch()
        self.hotkey_state_badge = make_label("", role="badge")
        header.addWidget(self.hotkey_state_badge)
        layout.addLayout(header)

        target_label = make_label("Stretch target", role="caption")
        self.hotkey_target_combo = QComboBox()
        self.hotkey_target_combo.setAccessibleName("Hotkey stretch target")
        self.hotkey_target_combo.setToolTip("Resolution the hotkey switches to from native")
        target_label.setBuddy(self.hotkey_target_combo)
        self.hotkey_target_combo.currentIndexChanged.connect(self.on_hotkey_target_changed)
        layout.addWidget(target_label)
        layout.addWidget(self.hotkey_target_combo)

        key_label = make_label("Hotkey", role="caption")
        key_row = QHBoxLayout()
        key_row.setSpacing(t.SPACE_SM)
        self.hotkey_mod_combo = QComboBox()
        self.hotkey_mod_combo.setAccessibleName("Hotkey modifier")
        for label, mods in HOTKEY_MODIFIERS:
            self.hotkey_mod_combo.addItem(label, mods)
        self.hotkey_input = QComboBox()
        self.hotkey_input.setAccessibleName("Hotkey key")
        self.hotkey_input.setFixedWidth(84)
        for function_key in range(1, 13):
            self.hotkey_input.addItem(f"F{function_key}", VK_F1 + function_key - 1)
        key_label.setBuddy(self.hotkey_mod_combo)
        _name, vk, mods = self.get_hotkey_config()
        self.hotkey_input.setCurrentIndex(vk - VK_F1)
        mod_index = self.hotkey_mod_combo.findData(mods)
        self.hotkey_mod_combo.setCurrentIndex(max(0, mod_index))
        self.hotkey_input.currentIndexChanged.connect(self.on_hotkey_changed)
        self.hotkey_mod_combo.currentIndexChanged.connect(self.on_hotkey_changed)
        key_row.addWidget(self.hotkey_mod_combo, 1)
        key_row.addWidget(self.hotkey_input)
        layout.addWidget(key_label)
        layout.addLayout(key_row)

        self.hotkey_hint = make_label("", role="caption", wrap=True)
        layout.addWidget(self.hotkey_hint)
        return panel

    def _build_custom_panel(self):
        panel = Panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)
        layout.setSpacing(t.SPACE_MD)

        header = QHBoxLayout()
        header.addWidget(SectionLabel("Custom Resolution"))
        header.addStretch()
        self.lbl_experimental = make_label("Quick picks", role="badge", tone="accent")
        header.addWidget(self.lbl_experimental)
        layout.addLayout(header)

        self.safe_res_combo = QComboBox()
        self.safe_res_combo.setAccessibleName("Common stretched resolution")
        for width, height in resolution.VALORANT_SAFE_RESOLUTIONS:
            ratio = resolution.get_aspect_ratio(width, height)
            self.safe_res_combo.addItem(f"{width} × {height}   ·   {ratio}", (width, height))
        self.safe_res_combo.currentIndexChanged.connect(self.on_safe_resolution_changed)
        layout.addWidget(self.safe_res_combo)

        self.experimental_toggle = QCheckBox("Enter any size (experimental)")
        self.experimental_toggle.toggled.connect(self.set_experimental_mode)
        layout.addWidget(self.experimental_toggle)

        size_row = QHBoxLayout()
        size_row.setSpacing(t.SPACE_SM)
        self.inp_rw = QLineEdit()
        self.inp_rw.setPlaceholderText("Width")
        self.inp_rw.setAccessibleName("Width in pixels")
        self.inp_rw.setValidator(QIntValidator(1, edid.MAX_DIMENSION))
        self.inp_rh = QLineEdit()
        self.inp_rh.setPlaceholderText("Height")
        self.inp_rh.setAccessibleName("Height in pixels")
        self.inp_rh.setValidator(QIntValidator(1, edid.MAX_DIMENSION))
        times = make_label("×", role="muted")
        self.inp_hz = QComboBox()
        self.inp_hz.setAccessibleName("Refresh rate")
        self.inp_hz.setFixedWidth(96)
        self.inp_rw.textChanged.connect(self.update_custom_hz_options)
        self.inp_rh.textChanged.connect(self.update_custom_hz_options)
        size_row.addWidget(self.inp_rw, 1)
        size_row.addWidget(times)
        size_row.addWidget(self.inp_rh, 1)
        size_row.addWidget(self.inp_hz)
        layout.addLayout(size_row)

        name_row = QHBoxLayout()
        name_row.setSpacing(t.SPACE_SM)
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Name (optional)")
        self.inp_name.setAccessibleName("Custom resolution name")
        self.inp_name.setMaxLength(40)
        self.btn_add = ActionButton("Add", primary=True)
        self.btn_add.setAccessibleName("Add custom resolution")
        self.btn_add.clicked.connect(self.add_custom_resolution)
        self.inp_name.returnPressed.connect(self.add_custom_resolution)
        name_row.addWidget(self.inp_name, 1)
        name_row.addWidget(self.btn_add)
        layout.addLayout(name_row)

        self.custom_error = make_label("", role="caption", tone="warning", wrap=True)
        self.custom_error.hide()
        layout.addWidget(self.custom_error)
        self.custom_safety_note = make_label("", role="caption", wrap=True)
        layout.addWidget(self.custom_safety_note)
        oled_warning = make_label("OLED panels: avoid stretch and monitor-toggle workflows.",
                                  role="caption", tone="warning", wrap=True)
        layout.addWidget(oled_warning)

        self.set_experimental_mode(False)
        return panel

    def _build_hardware_panel(self):
        panel = Panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)
        layout.setSpacing(t.SPACE_MD)
        layout.addWidget(SectionLabel("Hardware Monitors"))
        self.hw_box = Panel("inset")
        self.hw_layout = QVBoxLayout(self.hw_box)
        self.hw_layout.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        self.hw_layout.setSpacing(t.SPACE_SM)
        self.hw_layout.addWidget(make_label("Detecting monitors…", role="muted"))
        layout.addWidget(self.hw_box)
        layout.addWidget(make_label(
            "Turning a monitor device off can enable true stretch on laptops. Resolution changes never touch these.",
            role="caption", wrap=True))
        return panel

    def _build_action_bar(self):
        bar = QWidget()
        bar.setObjectName("ActionBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_MD, t.SPACE_LG, t.SPACE_MD)
        layout.setSpacing(t.SPACE_MD)

        self.toast = QLabel()
        self.toast.setObjectName("Toast")
        self.toast.setTextFormat(Qt.TextFormat.PlainText)
        self.toast.setAccessibleName("Status")
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self.toast.setText(""))

        self.reset_btn = ActionButton("Restore Native")
        self.reset_btn.setToolTip(f"Restore the saved native resolution. Monitors are not changed. ({RESTORE_HOTKEY_TEXT} anywhere)")
        self.reset_btn.clicked.connect(lambda: self.reset_res(enable_monitors=False))
        self.reset_mon_btn = ActionButton("Restore Native + Enable Monitors", destructive=True)
        self.reset_mon_btn.setToolTip("Restore the native resolution and turn every monitor device back on")
        self.reset_mon_btn.clicked.connect(lambda: self.reset_res(enable_monitors=True))

        layout.addWidget(self.toast, 1)
        layout.addWidget(self.reset_btn)
        layout.addWidget(self.reset_mon_btn)
        return bar

    def _build_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_file = os.path.join(asset_base_path(), "icon.png")
        if os.path.exists(icon_file):
            self.tray_icon.setIcon(QIcon(icon_file))
        self.tray_icon.setToolTip("EasyRes")
        self.tray_menu = QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------
    def notify(self, text, tone=None, ms=t.TOAST_MS):
        self.toast.setText(text)
        styles.set_props(self.toast, tone=tone or "")
        self._toast_timer.stop()
        if ms:
            self._toast_timer.start(ms)
        if tone == "warning" and not self.isVisible() and hasattr(self, "tray_icon"):
            self.tray_icon.showMessage("EasyRes", text, QSystemTrayIcon.MessageIcon.Warning, 4000)

    def set_busy(self, busy, text=None):
        self._busy = busy
        self.presets_grid_widget.setEnabled(not busy)
        self.btn_add.setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
            if text:
                self.notify(text, ms=0)
        else:
            QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------------
    # Hotkeys
    # ------------------------------------------------------------------
    def init_hotkeys(self):
        app = QApplication.instance()
        self.hotkey_filter = HotkeyEventFilter({
            HOTKEY_ID_TOGGLE: self.toggle_stretch_native_hotkey,
            HOTKEY_ID_RESTORE: lambda: self.reset_res(enable_monitors=False),
        })
        app.installNativeEventFilter(self.hotkey_filter)
        user32 = ctypes.windll.user32
        user32.UnregisterHotKey(None, HOTKEY_ID_RESTORE)
        self.restore_hotkey_registered = bool(
            user32.RegisterHotKey(None, HOTKEY_ID_RESTORE, RESTORE_HOTKEY_MODS | MOD_NOREPEAT, RESTORE_HOTKEY_VK)
        )
        self.apply_hotkey_setting()

    def get_hotkey_config(self):
        vk = _as_int(self.settings.value("toggle_hotkey_vk", DEFAULT_HOTKEY_VK))
        if vk is None or not (VK_F1 <= vk <= VK_F12):
            vk = DEFAULT_HOTKEY_VK
        mods = _as_int(self.settings.value("toggle_hotkey_mods", 0)) or 0
        if mods not in {m for _label, m in HOTKEY_MODIFIERS}:
            mods = 0
        key = f"F{vk - VK_F1 + 1}"
        mod_label = next(label for label, m in HOTKEY_MODIFIERS if m == mods)
        name = key if not mods else f"{mod_label}+{key}"
        return name, vk, mods

    def apply_hotkey_setting(self):
        user32 = ctypes.windll.user32
        user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
        key_name, vk, mods = self.get_hotkey_config()
        self.settings.setValue("toggle_hotkey_name", key_name)
        self.hotkey_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_TOGGLE, mods | MOD_NOREPEAT, vk))
        self._sync_hotkey_labels()
        self.update_tray_menu()

    def on_hotkey_changed(self, _index=None):
        vk = self.hotkey_input.currentData()
        mods = self.hotkey_mod_combo.currentData()
        if not isinstance(vk, int) or not isinstance(mods, int):
            return
        self.settings.setValue("toggle_hotkey_vk", vk)
        self.settings.setValue("toggle_hotkey_mods", mods)
        self.apply_hotkey_setting()
        name, _vk, _mods = self.get_hotkey_config()
        if self.hotkey_registered:
            self.notify(f"Quick toggle is now {name}.")
        else:
            self.notify(f"{name} is taken by another app. Pick a different key.", tone="warning")

    def _sync_hotkey_labels(self):
        if not hasattr(self, "hotkey_state_badge"):
            return
        key_name, _vk, _mods = self.get_hotkey_config()
        if self.hotkey_registered:
            self.hotkey_state_badge.setText(f"{key_name}  ·  Ready")
            set_tone(self.hotkey_state_badge, "accent")
            self.hotkey_hint.setText(
                f"{key_name} switches between native and the stretch target. Monitors are never changed. "
                f"{RESTORE_HOTKEY_TEXT} restores native from anywhere."
                if self.restore_hotkey_registered else
                f"{key_name} switches between native and the stretch target. Monitors are never changed."
            )
        else:
            self.hotkey_state_badge.setText(f"{key_name}  ·  Unavailable")
            set_tone(self.hotkey_state_badge, "warning")
            self.hotkey_hint.setText(f"{key_name} is already used by another app. Choose another key or add a modifier.")

    def toggle_stretch_native_hotkey(self):
        if self._busy:
            return
        dev = self.get_dev_name()
        if not dev:
            return
        current = resolution.get_current_resolution(dev)
        native = resolution.get_registry_resolution(dev)
        if not current or not native:
            return

        if not self._is_native(current, native):
            self.last_stretch_modes[dev] = {"w": current["width"], "h": current["height"], "hz": current.get("hz")}
            self._save_last_stretch_modes()
            self.reset_res(enable_monitors=False)
            return

        target = self._load_hotkey_target() or self.last_stretch_modes.get(dev)
        w = _as_int(target.get("w")) if isinstance(target, dict) else None
        h = _as_int(target.get("h")) if isinstance(target, dict) else None
        hz = _as_int(target.get("hz")) if isinstance(target, dict) and target.get("hz") is not None else None
        if not w or not h or w <= 0 or h <= 0:
            self.notify("Pick a stretch target under Quick Toggle, or apply a stretched mode once.", tone="warning")
            return
        self.change_res(w, h, hz, confirm=False)

    # ------------------------------------------------------------------
    # First run, settings, updates
    # ------------------------------------------------------------------
    def check_first_run(self):
        if not self.settings.value("tutorial_shown", False, type=bool):
            self.settings.setValue("tutorial_shown", True)
            self.show_tutorial()

    def show_tutorial(self):
        TutorialDialog(self).exec()

    def show_settings(self):
        SettingsDialog(self.settings, self).exec()

    def _on_background_release(self, release):
        latest_version = release.get("tag_name", "").lstrip("v")
        if latest_version and updater.is_newer_version(latest_version, updater.CURRENT_VERSION):
            self.show_update_notification(release)

    def show_update_notification(self, release):
        self.available_release = release
        version = release.get("tag_name", "").lstrip("v")
        if not self._update_in_progress:
            self.update_btn.setText(f"Update to {version}")
            self.update_btn.setAccessibleName(f"Update EasyRes to version {version}")
            self.update_btn.setEnabled(True)
        self.update_btn.show()

    def prompt_update(self):
        release = self.available_release
        if not release:
            return
        if not updater.can_self_update():
            themed_message_box(self, "Update available",
                               "Automatic updates work in the packaged EasyRes.exe build. "
                               "Download the new version from the GitHub release page.")
            return
        try:
            asset = updater.select_windows_asset(release)
        except updater.UpdateError as exc:
            self.notify(str(exc), tone="warning")
            return

        version = release.get("tag_name", "").lstrip("v")
        size_mb = (_as_int(asset.get("size")) or 0) / (1024 * 1024)
        reply = themed_message_box(
            self,
            f"Install EasyRes {version}?",
            f"The update is {size_mb:.1f} MB. EasyRes will download and verify it, then close, "
            "replace itself, and restart. If anything fails, the current version is kept.",
            QMessageBox.Icon.Question,
            StandardButton.Yes | StandardButton.Cancel,
            labels={StandardButton.Yes: "Install and Restart", StandardButton.Cancel: "Later"},
        )
        if reply == StandardButton.Yes:
            self.start_update(release)

    def start_update(self, release):
        if self._update_in_progress:
            return
        self._update_in_progress = True
        self.show_update_notification(release)
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Downloading 0%")

        def download():
            asset = updater.select_windows_asset(release)
            return updater.download_asset(asset, self.update_progress.emit)

        run_async(download, on_done=self.on_update_ready, on_error=self.on_update_failed)

    def on_update_progress(self, percent):
        self.update_btn.setText(f"Downloading {percent}%")

    def on_update_ready(self, downloaded_update):
        self.update_btn.setText("Restarting…")
        try:
            updater.launch_replacement(downloaded_update)
        except updater.UpdateError as exc:
            updater.discard_download(downloaded_update)
            self.on_update_failed(str(exc))
            return
        # The Qt event loop stops on quit, so the fallback exit needs a thread timer.
        force_exit = threading.Timer(3.0, lambda: os._exit(0))
        force_exit.daemon = True
        force_exit.start()
        self._quit_app()

    def on_update_failed(self, message):
        self._update_in_progress = False
        version = (self.available_release or {}).get("tag_name", "").lstrip("v")
        self.update_btn.setText(f"Update to {version}" if version else "Update available")
        self.update_btn.setEnabled(True)
        themed_message_box(self, "Update failed", f"{message}\n\nYour current version was not changed.",
                           QMessageBox.Icon.Warning)

    # ------------------------------------------------------------------
    # Quit / close
    # ------------------------------------------------------------------
    def _quit_app(self):
        self._quitting = True
        user32 = ctypes.windll.user32
        user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
        user32.UnregisterHotKey(None, HOTKEY_ID_RESTORE)
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return

        ask_close = self.settings.value("ask_close", True, type=bool)
        if not ask_close:
            if self.settings.value("minimize_to_tray", False, type=bool):
                event.ignore()
                self.hide()
                self._notify_tray_once()
            else:
                event.accept()
                self._quit_app()
            return

        reply, dont_ask = themed_message_box(
            self,
            "Keep EasyRes running?",
            "In the tray, the quick toggle and Restore Native hotkeys keep working.",
            QMessageBox.Icon.Question,
            StandardButton.Yes | StandardButton.No | StandardButton.Cancel,
            "Remember my choice",
            labels={StandardButton.Yes: "Minimize to Tray", StandardButton.No: "Quit"},
        )

        if reply == StandardButton.Yes:
            if dont_ask:
                self.settings.setValue("minimize_to_tray", True)
                self.settings.setValue("ask_close", False)
            event.ignore()
            self.hide()
            self._notify_tray_once()
        elif reply == StandardButton.No:
            if dont_ask:
                self.settings.setValue("minimize_to_tray", False)
                self.settings.setValue("ask_close", False)
            event.accept()
            self._quit_app()
        else:
            event.ignore()

    def _notify_tray_once(self):
        if not self.settings.value("tray_hint_shown", False, type=bool):
            self.settings.setValue("tray_hint_shown", True)
            self.tray_icon.showMessage("EasyRes is still running",
                                       "Right-click the tray icon for quick switching.",
                                       QSystemTrayIcon.MessageIcon.Information, 4000)

    # ------------------------------------------------------------------
    # Display state
    # ------------------------------------------------------------------
    def get_dev_name(self):
        return self.current_display.get("name") if self.current_display else None

    @staticmethod
    def _is_native(current, native):
        return bool(
            current and native and
            current["width"] == native["width"] and
            current["height"] == native["height"] and
            current.get("hz") == native.get("hz")
        )

    def on_monitor_changed(self, index):
        dev_name = self.mon_combo.itemData(index)
        self.current_display = next((d for d in self.displays if d.get("name") == dev_name), self.current_display)
        if self.current_display:
            self.refresh_display()
            self.load_presets()
            self.on_safe_resolution_changed()

    def refresh_display(self):
        self._update_status_band()
        QTimer.singleShot(100, self.adjust_window_size)

    def _update_status_band(self):
        dev = self.get_dev_name()
        info = resolution.get_current_resolution(dev) if dev else None
        native = resolution.get_registry_resolution(dev) if dev else None
        if info:
            self.stat_resolution.set_value(f"{info['width']} × {info['height']}")
            self.stat_refresh.set_value(f"{info.get('hz') or '--'} Hz")
        else:
            self.stat_resolution.set_value("No display", warning=True)
            self.stat_refresh.set_value("--")

        if not info or not native:
            self.stat_mode.set_value("--")
        elif self._is_native(info, native):
            self.stat_mode.set_value("Native")
        else:
            native_ratio = native["width"] / native["height"] if native["height"] else 0
            current_ratio = info["width"] / info["height"] if info["height"] else 0
            stretched = abs(native_ratio - current_ratio) > 0.02
            self.stat_mode.set_value("Stretched" if stretched else "Scaled", accent=True)

        if not self.hw_monitors:
            self.stat_monitor.set_value("Not found")
            return
        off = sum(1 for m in self.hw_monitors if not self._monitor_is_on(m))
        if off:
            self.stat_monitor.set_value(f"{off} off", warning=True)
        else:
            self.stat_monitor.set_value("All on")

    # ------------------------------------------------------------------
    # Resolution list
    # ------------------------------------------------------------------
    def _aspect_bucket(self, width, height):
        if not width or not height:
            return "Other"
        ratio = width / height
        for label, target in (("16:9", 16 / 9), ("16:10", 16 / 10), ("4:3", 4 / 3), ("5:4", 5 / 4), ("21:9", 21 / 9)):
            if abs(ratio - target) < 0.03:
                return label
        return "Other"

    def load_presets(self):
        dev_name = self.get_dev_name()
        modes = resolution.get_all_resolutions(dev_name) if dev_name else []
        rates = {}
        for w, h, hz in modes:
            if hz > 0:
                rates.setdefault((w, h), set()).add(hz)
        unique_modes = []
        seen = set()
        for w, h, _hz in modes:
            if (w, h) in seen:
                continue
            seen.add((w, h))
            unique_modes.append((w, h))

        if unique_modes:
            self._preset_cache[dev_name] = (unique_modes, rates)
        elif dev_name in self._preset_cache:
            unique_modes, rates = self._preset_cache[dev_name]
            self._schedule_preset_retry(dev_name)
        elif dev_name:
            self._schedule_preset_retry(dev_name)
        self._rates_by_mode = {key: sorted(value, reverse=True) for key, value in rates.items()}

        hidden = set(self._load_hidden())
        final_presets = []
        for c in self._load_customs():
            final_presets.append((c["w"], c["h"], "My Modes", c["name"], True, c["hz"]))
        for w, h in unique_modes:
            if f"{w}x{h}" not in hidden:
                final_presets.append((w, h, self._aspect_bucket(w, h), "", False, None))

        self._final_presets = final_presets
        self.layout_presets_grid(force=True)
        self._refresh_hotkey_targets()
        if dev_name in self._preset_retry_pending and unique_modes:
            self._preset_retry_pending.discard(dev_name)
        self.update_tray_menu()

    def _schedule_preset_retry(self, dev_name):
        if dev_name not in self._preset_retry_pending:
            self._preset_retry_pending.add(dev_name)
            QTimer.singleShot(750, lambda: self._retry_preset_load(dev_name))

    def _retry_preset_load(self, dev_name):
        self._preset_retry_pending.discard(dev_name)
        if dev_name == self.get_dev_name():
            self.load_presets()

    def _refresh_hotkey_targets(self):
        self.hotkey_target_combo.blockSignals(True)
        self.hotkey_target_combo.clear()
        self.hotkey_target_combo.addItem("Last stretched mode", None)
        saved_target = self._load_hotkey_target()
        idx_to_select = 0
        for w, h, _ratio, label, is_custom, hz in self._final_presets:
            hz_text = f" @ {hz} Hz" if hz else ""
            name = f"{label}  ·  " if is_custom else ""
            self.hotkey_target_combo.addItem(f"{name}{w} × {h}{hz_text}", {"w": w, "h": h, "hz": hz})
            if saved_target and saved_target["w"] == w and saved_target["h"] == h and saved_target["hz"] == hz:
                idx_to_select = self.hotkey_target_combo.count() - 1
        self.hotkey_target_combo.setCurrentIndex(idx_to_select)
        self.hotkey_target_combo.blockSignals(False)

    def on_hotkey_target_changed(self, _index):
        self.settings.setValue("hotkey_target_res", self.hotkey_target_combo.currentData())

    def _column_count(self):
        width = self.mode_scroll.viewport().width() if hasattr(self, "mode_scroll") else 0
        if width <= 0:
            return 3
        return max(2, min(6, (width + t.SPACE_SM) // (t.MODE_TILE_MIN_WIDTH + t.SPACE_SM)))

    def _relayout_if_columns_changed(self):
        if hasattr(self, "presets_grid") and self._column_count() != self._columns:
            self.layout_presets_grid(force=False)

    def _matches_filter(self, preset, text):
        if not text:
            return True
        w, h, ratio, label, _is_custom, hz = preset
        rates = self._rates_by_mode.get((w, h), [])
        haystack = " ".join([f"{w}x{h}", f"{w} x {h}", f"{w}×{h}", str(w), str(h), ratio, label or "",
                             *(f"{r}" for r in ([hz] if hz else rates))]).lower()
        return all(part in haystack for part in text.lower().split())

    def layout_presets_grid(self, force=True):
        """Build tiles when data changes (force) or only re-flow them when
        the column count changes (resize)."""
        if not hasattr(self, "presets_grid"):
            return
        columns = self._column_count()
        if force:
            self._build_tiles()
        self._columns = columns

        while self.presets_grid.count():
            self.presets_grid.takeAt(0)
        for row in range(self.presets_grid.rowCount()):
            self.presets_grid.setRowStretch(row, 0)

        row_index = 0
        for group in ASPECT_ORDER:
            tiles = [tile for tile_group, tile in self._tiles if tile_group == group and not tile.isHidden()]
            label = self._group_labels.get(group)
            if not tiles:
                if label:
                    label.hide()
                continue
            label.show()
            self.presets_grid.addWidget(label, row_index, 0, 1, columns)
            row_index += 1
            for index, tile in enumerate(tiles):
                self.presets_grid.addWidget(tile, row_index + index // columns, index % columns)
            row_index += (len(tiles) + columns - 1) // columns
        for col in range(6):
            self.presets_grid.setColumnStretch(col, 1 if col < columns else 0)

        visible = sum(1 for _g, tile in self._tiles if not tile.isHidden())
        self.empty_label.setVisible(visible == 0)
        self.presets_grid.addWidget(self.empty_label, row_index, 0, 1, columns)
        self.presets_grid.setRowStretch(row_index + 1, 1)

        total = len(self._tiles)
        self.mode_count_label.setText(f"{visible} of {total}" if visible != total else f"{total} modes")

    def _apply_filter(self, _text=None):
        filter_text = self.mode_filter.text().strip()
        presets = getattr(self, "_final_presets", [])
        for preset, (_group, tile) in zip(presets, self._tiles):
            tile.setVisible(self._matches_filter(preset, filter_text))
        self._update_empty_text(filter_text)
        self.layout_presets_grid(force=False)

    def _update_empty_text(self, filter_text):
        if filter_text:
            self.empty_label.setText(f"No resolutions match “{filter_text}”.")
        else:
            self.empty_label.setText("No modes reported yet. EasyRes retries automatically after a display or driver change.")

    def _build_tiles(self):
        for _group, tile in self._tiles:
            tile.hide()
            tile.deleteLater()
        for label in self._group_labels.values():
            label.hide()
            label.deleteLater()
        self._tiles = []
        self._group_labels = {}
        if not hasattr(self, "empty_label"):
            self.empty_label = make_label("", role="muted", wrap=True, parent=self.presets_grid_widget)

        dev = self.get_dev_name()
        info = resolution.get_current_resolution(dev) if dev else None
        curr = (info["width"], info["height"], info.get("hz")) if info else (0, 0, None)
        filter_text = self.mode_filter.text().strip() if hasattr(self, "mode_filter") else ""

        for preset in getattr(self, "_final_presets", []):
            w, h, ratio, label, is_custom, hz = preset
            group = ratio if ratio in ASPECT_ORDER else "Other"
            is_active = (w == curr[0] and h == curr[1] and (hz is None or hz == curr[2]))
            tile = ModeRow(w, h, ratio, label, is_custom, hz, is_active=is_active,
                           rates=self._rates_by_mode.get((w, h), []), parent=self.presets_grid_widget)
            tile.apply_requested.connect(self.change_res)
            tile.save_requested.connect(self.save_mode)
            tile.delete_requested.connect(self.delete_custom_resolution)
            tile.active_clicked.connect(lambda: self.notify("That resolution is already active."))
            tile.setVisible(self._matches_filter(preset, filter_text))
            self._tiles.append((group, tile))
            if group not in self._group_labels:
                self._group_labels[group] = SectionLabel(group, self.presets_grid_widget)

        self._update_empty_text(filter_text)

    # ------------------------------------------------------------------
    # Applying resolutions
    # ------------------------------------------------------------------
    def change_res(self, w, h, hz=None, confirm=True):
        if self._busy:
            self.notify("Hold on, still applying the last change.")
            return
        dev = self.get_dev_name()
        if not dev:
            return
        previous = resolution.get_current_resolution(dev)
        mode_text = f"{w} × {h}" + (f" @ {hz} Hz" if hz else "")
        self.set_busy(True, f"Switching to {mode_text}…")

        def done(ok):
            self.set_busy(False)
            if not ok:
                self.notify(f"Your display driver rejected {mode_text}. Nothing changed.", tone="warning")
                self.refresh_display()
                return
            native = resolution.get_registry_resolution(dev)
            applied = resolution.get_current_resolution(dev) or {"width": w, "height": h, "hz": hz}
            if native and not self._is_native(applied, native):
                self.last_stretch_modes[dev] = {"w": w, "h": h, "hz": hz}
                self._save_last_stretch_modes()
            self.refresh_display()
            self.load_presets()
            self.notify(f"Switched to {mode_text}.", tone="success")

            changed = previous and (previous["width"], previous["height"]) != (w, h)
            if confirm and changed and self.settings.value("ask_apply_res", True, type=bool):
                self._confirm_or_revert(mode_text, previous)

        def failed(message):
            self.set_busy(False)
            self.notify(f"Couldn't switch: {message}", tone="warning")

        run_async(resolution.set_resolution, w, h, hz, dev, on_done=done, on_error=failed)

    def _confirm_or_revert(self, mode_text, previous):
        dialog = RevertDialog(mode_text, parent=self if self.isVisible() else None)
        self._revert_dialog = dialog
        self._busy = True
        try:
            dialog.exec()
        finally:
            self._busy = False
            self._revert_dialog = None
        if dialog.keep or getattr(dialog, "cancelled_by_restore", False):
            return
        self.change_res(previous["width"], previous["height"], previous.get("hz"), confirm=False)
        self.notify("Reverted to your previous resolution.")

    def reset_res(self, enable_monitors=False):
        if self._revert_dialog is not None:
            # Restore Native wins over a pending keep/revert countdown.
            self._revert_dialog.cancelled_by_restore = True
            self._revert_dialog.reject()
        dev = self.get_dev_name()
        instance_ids = [m.get("Instance ID") for m in self.hw_monitors if m.get("Instance ID")] if enable_monitors else []
        self.notify("Restoring native resolution…", ms=0)

        def work():
            monitor_failures = 0
            if enable_monitors:
                for instance_id in instance_ids:
                    if not resolution.set_hardware_monitor_state(instance_id, True):
                        monitor_failures += 1
                resolution.set_monitor_state(dev, True)
            return resolution.reset_resolution(dev), monitor_failures

        def done(result):
            ok, monitor_failures = result
            self.refresh_display()
            self.load_presets()
            if enable_monitors:
                self.refresh_hardware_monitors()
            if not ok:
                self.notify("Windows didn't accept the native mode. Try again or use Windows display settings.", tone="warning")
            elif monitor_failures:
                self.notify(f"Native restored, but {monitor_failures} monitor(s) couldn't be enabled.", tone="warning")
            else:
                self.notify("Native resolution restored" + (" and monitors enabled." if enable_monitors else "."), tone="success")

        run_async(work, on_done=done, on_error=lambda msg: self.notify(f"Restore failed: {msg}", tone="warning"))

    # ------------------------------------------------------------------
    # Saved modes
    # ------------------------------------------------------------------
    def save_mode(self, w, h, hz):
        customs = self._load_customs()
        if any(c["w"] == w and c["h"] == h and c["hz"] == hz for c in customs):
            self.notify(f"{w} × {h} @ {hz} Hz is already in My Modes.")
            return
        customs.append({"name": f"{w}×{h} @ {hz} Hz", "w": w, "h": h, "hz": hz})
        self._save_customs(customs)
        self.load_presets()
        self.notify(f"Saved {w} × {h} @ {hz} Hz to My Modes.", tone="success")

    def delete_custom_resolution(self, name, w, h, is_custom):
        if is_custom:
            reply = themed_message_box(
                self, f"Remove “{name}”?",
                "It will be removed from My Modes. Any EDID injection stays in place; use Settings → "
                "Restore EDID to undo that.",
                QMessageBox.Icon.Question, StandardButton.Yes | StandardButton.Cancel,
                labels={StandardButton.Yes: "Remove"},
            )
            if reply == StandardButton.Yes:
                self._save_customs([c for c in self._load_customs() if c["name"] != name])
                self.load_presets()
                self.notify(f"Removed “{name}”.")
        else:
            hidden = self._load_hidden()
            hidden.append(f"{w}x{h}")
            self.settings.setValue("hidden_presets", hidden)
            self.load_presets()
            self.notify(f"Hid {w} × {h}. Settings → Show Hidden Modes brings it back.")

    # ------------------------------------------------------------------
    # Custom resolution (EDID)
    # ------------------------------------------------------------------
    def on_safe_resolution_changed(self, _index=None):
        if not hasattr(self, "experimental_toggle") or self.experimental_toggle.isChecked():
            return
        data = self.safe_res_combo.currentData()
        if not data:
            return
        width, height = data
        self.inp_rw.setText(str(width))
        self.inp_rh.setText(str(height))
        self.update_custom_hz_options()

    def set_experimental_mode(self, enabled):
        self.safe_res_combo.setEnabled(not enabled)
        self.inp_rw.setEnabled(enabled)
        self.inp_rh.setEnabled(enabled)
        self._set_custom_error("")
        if enabled:
            self.lbl_experimental.setText("Experimental")
            set_tone(self.lbl_experimental, "warning")
            self.custom_safety_note.setText(
                "Non-standard sizes are unsupported and can fail or show black bars. "
                f"Sizes {edid.MIN_DIMENSION}–{edid.MAX_DIMENSION} px.")
            self.inp_rw.setFocus()
        else:
            self.lbl_experimental.setText("Quick picks")
            set_tone(self.lbl_experimental, "accent")
            self.custom_safety_note.setText(
                "Common 4:3 and 5:4 stretched modes. Adding one writes an EDID override and briefly "
                "restarts your graphics driver.")
            self.on_safe_resolution_changed()

    def _set_custom_error(self, text, fields=()):
        self.custom_error.setText(text)
        self.custom_error.setVisible(bool(text))
        for field in (self.inp_rw, self.inp_rh, self.inp_name):
            styles.set_props(field, error=field in fields)

    def update_custom_hz_options(self):
        if not hasattr(self, "inp_hz"):
            return
        width, height = _as_int(self.inp_rw.text()), _as_int(self.inp_rh.text())
        previous = self.inp_hz.currentData()
        self.inp_hz.blockSignals(True)
        self.inp_hz.clear()
        rates = []
        if width and height:
            rates = resolution.get_monitor_refresh_rates(width, height, self.get_dev_name())
            if rates:
                self.inp_hz.setToolTip("Refresh rates your monitor reports for this size")
            else:
                current = resolution.get_current_resolution(self.get_dev_name())
                if current and current.get("hz"):
                    rates = [current["hz"]]
                self.inp_hz.setToolTip("Not currently exposed by Windows; using your current refresh rate")
        if not rates:
            self.inp_hz.addItem("Hz", None)
        for rate in rates:
            self.inp_hz.addItem(f"{rate} Hz", rate)
        if previous in rates:
            self.inp_hz.setCurrentIndex(rates.index(previous))
        self.inp_hz.blockSignals(False)

    def add_custom_resolution(self):
        if self._busy:
            return
        w, h = _as_int(self.inp_rw.text().strip()), _as_int(self.inp_rh.text().strip())
        hz = self.inp_hz.currentData()
        if not w or not h:
            self._set_custom_error("Enter a width and height.", fields=[f for f, v in ((self.inp_rw, w), (self.inp_rh, h)) if not v])
            return
        if hz is None:
            self._set_custom_error("Choose a refresh rate.")
            return
        try:
            edid.validate_mode(w, h, int(hz))
            edid.generate_cvt_rb(w, h, int(hz))
        except edid.EdidError as exc:
            self._set_custom_error(str(exc), fields=[self.inp_rw, self.inp_rh])
            return

        safe_catalog = (w, h) in resolution.VALORANT_SAFE_RESOLUTIONS
        if not self.experimental_toggle.isChecked() and not safe_catalog:
            self._set_custom_error("Pick a listed mode, or turn on “Enter any size”.")
            return

        name = self.inp_name.text().strip() or f"{w}×{h} @ {hz} Hz"
        customs = self._load_customs()
        if any(c["name"] == name for c in customs):
            self._set_custom_error("A saved mode already uses that name.", fields=[self.inp_name])
            return
        if any(c["w"] == w and c["h"] == h and c["hz"] == hz for c in customs):
            self._set_custom_error(f"{w} × {h} @ {hz} Hz is already in My Modes.")
            return
        self._set_custom_error("")

        aspect = resolution.get_aspect_ratio(w, h)
        if aspect == "Experimental":
            title = f"Add experimental {w} × {h}?"
            text = ("This isn't a standard 4:3 or 5:4 stretch. It may fail in games, show black bars, or leave the "
                    "screen blank until you press Restore Native.\n\n")
        else:
            title = f"Add {w} × {h} @ {hz} Hz?"
            text = ""
        text += ("EasyRes will write an EDID override for this monitor and restart the graphics driver. "
                 "Your screen will flash black for a few seconds. The original EDID is backed up, and you can "
                 "restore it from Settings.")
        reply = themed_message_box(self, title, text, QMessageBox.Icon.Warning,
                                   StandardButton.Yes | StandardButton.Cancel,
                                   labels={StandardButton.Yes: "Add and Restart Driver"})
        if reply != StandardButton.Yes:
            return

        dev_id = self.current_display.get("device_id") if self.current_display else None
        backups = self._edid_backups()
        self.set_busy(True, "Writing EDID override and restarting the graphics driver…")

        def work():
            active_ids = edid.get_active_monitor_device_ids()
            target_id = edid.match_monitor_instance(dev_id, active_ids)
            if not target_id:
                raise RuntimeError("Couldn't tell which monitor to modify, so nothing was changed.")
            current = edid.get_edid(target_id)
            if not current:
                raise RuntimeError("Couldn't read this monitor's EDID. Nothing was changed.")
            if edid.is_resolution_injected(current, w, h, int(hz)):
                return {"restarted": False, "driver_ok": True, "target": target_id, "backup": None}
            backup_hex = backups.get(target_id)
            original = bytes.fromhex(backup_hex) if backup_hex else bytes(current)
            new_edid = edid.inject_resolution(original, w, h, int(hz))
            if not new_edid:
                raise RuntimeError("This monitor's EDID has no free slot for a custom timing. Nothing was changed.")
            if not edid.set_edid(target_id, new_edid):
                raise RuntimeError("Windows refused the EDID write. Nothing was changed.")
            driver_ok = driver.restart_graphics_driver()
            return {"restarted": True, "driver_ok": driver_ok, "target": target_id,
                    "backup": None if backup_hex else original.hex()}

        def done(result):
            if result.get("backup"):
                saved = self._edid_backups()
                saved[result["target"]] = result["backup"]
                self.settings.setValue("edid_backups", saved)
            customs_now = self._load_customs()
            customs_now.append({"name": name, "w": w, "h": h, "hz": hz})
            self._save_customs(customs_now)
            self.inp_name.clear()
            self.on_safe_resolution_changed()

            def finish():
                self.set_busy(False)
                self.load_presets()
                self.refresh_display()
                if result.get("restarted") and not result.get("driver_ok"):
                    self.notify("Mode added, but the driver restart didn't finish. Reboot if the mode is missing.",
                                tone="warning", ms=0)
                else:
                    self.notify(f"Added {name}.", tone="success")

            if result.get("restarted"):
                self.notify("Waiting for the display driver…", ms=0)
                QTimer.singleShot(4000, finish)
            else:
                finish()

        def failed(message):
            self.set_busy(False)
            self._set_custom_error(message)
            self.notify("Custom resolution not added.", tone="warning")

        run_async(work, on_done=done, on_error=failed)

    def restore_original_edid(self):
        backups = self._edid_backups()
        if not backups or self._busy:
            return
        reply = themed_message_box(
            self, "Restore original EDID?",
            "EasyRes will write back the EDID it saved before your first custom resolution and restart the "
            "graphics driver. Injected custom modes will stop working; they stay in My Modes until you remove them.",
            QMessageBox.Icon.Warning, StandardButton.Yes | StandardButton.Cancel,
            labels={StandardButton.Yes: "Restore and Restart Driver"},
        )
        if reply != StandardButton.Yes:
            return
        self.set_busy(True, "Restoring original EDID…")

        def work():
            failures = [target for target, value in backups.items() if not edid.set_edid(target, bytes.fromhex(value))]
            driver_ok = driver.restart_graphics_driver()
            return failures, driver_ok

        def done(result):
            failures, driver_ok = result
            if not failures:
                self.settings.remove("edid_backups")

            def finish():
                self.set_busy(False)
                self.load_presets()
                self.refresh_display()
                if failures:
                    self.notify("Some EDIDs couldn't be restored. Try again.", tone="warning")
                elif not driver_ok:
                    self.notify("EDID restored. Reboot to finish.", tone="warning", ms=0)
                else:
                    self.notify("Original EDID restored.", tone="success")

            QTimer.singleShot(4000, finish)

        def failed(message):
            self.set_busy(False)
            self.notify(f"EDID restore failed: {message}", tone="warning")

        run_async(work, on_done=done, on_error=failed)

    # ------------------------------------------------------------------
    # Hardware monitors
    # ------------------------------------------------------------------
    @staticmethod
    def _monitor_is_on(monitor):
        return monitor.get("Status", "").lower() != "disabled"

    def refresh_hardware_monitors(self):
        run_async(resolution.get_hardware_monitors, on_done=self._populate_hardware_monitors,
                  on_error=lambda _msg: self._populate_hardware_monitors([]))

    def _populate_hardware_monitors(self, monitors):
        self.hw_monitors = monitors or []
        while self.hw_layout.count():
            item = self.hw_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        self.hw_toggles = []

        if not self.hw_monitors:
            self.hw_layout.addWidget(make_label("No monitor devices found.", role="muted"))
        for monitor in self.hw_monitors:
            instance_id = monitor.get("Instance ID", "")
            description = monitor.get("Device Description") or "Unknown monitor"
            is_on = self._monitor_is_on(monitor)

            row = QHBoxLayout()
            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            name = make_label(description, role="strong")
            name.setToolTip(instance_id)
            state = make_label("On" if is_on else "Off", role="caption", tone=None if is_on else "warning")
            text_col.addWidget(name)
            text_col.addWidget(state)
            toggle = PremiumToggle(f"{description} power")
            toggle.setChecked(is_on, emit=False)
            toggle.toggled.connect(lambda checked, iid=instance_id, tgl=toggle, lbl=state, desc=description:
                                   self._set_monitor_power(iid, checked, tgl, lbl, desc))
            row.addLayout(text_col, 1)
            row.addWidget(toggle)
            self.hw_layout.addLayout(row)
            self.hw_toggles.append((instance_id, toggle))

        any_off = any(not self._monitor_is_on(m) for m in self.hw_monitors)
        set_tone(self.hw_box, "warning" if any_off else None)
        self._update_status_band()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.layout():
                self._clear_layout(item.layout())
            if item.widget():
                item.widget().deleteLater()

    def _set_monitor_power(self, instance_id, enable, toggle, state_label, description):
        toggle.setEnabled(False)
        state_label.setText("Turning on…" if enable else "Turning off…")

        def done(ok):
            if not ok:
                self.notify(f"Windows couldn't turn {description} {'on' if enable else 'off'}.", tone="warning")
            else:
                self.notify(f"{description} turned {'on' if enable else 'off'}.", tone="success")
            self.refresh_hardware_monitors()
            self.refresh_display()

        run_async(resolution.set_hardware_monitor_state, instance_id, enable, on_done=done,
                  on_error=lambda msg: done(False))

    # ------------------------------------------------------------------
    # Tray
    # ------------------------------------------------------------------
    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def update_tray_menu(self):
        if not hasattr(self, "tray_menu"):
            return
        self.tray_menu.clear()

        show_action = self.tray_menu.addAction("Open EasyRes")
        show_action.triggered.connect(lambda: self.on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger))

        hotkey_name, _vk, _mods = self.get_hotkey_config()
        hotkey_action = self.tray_menu.addAction(f"Toggle Stretch / Native\t{hotkey_name}")
        hotkey_action.triggered.connect(self.toggle_stretch_native_hotkey)
        self.tray_menu.addSeparator()

        modes_menu = self.tray_menu.addMenu("Switch Resolution")
        customs = self._load_customs()
        for c in customs:
            hz_text = f" @ {c['hz']} Hz" if c["hz"] else ""
            act = modes_menu.addAction(f"{c['name']}  ({c['w']} × {c['h']}{hz_text})")
            act.triggered.connect(lambda _checked=False, cw=c["w"], ch=c["h"], chz=c["hz"]: self.change_res(cw, ch, chz))
        available = {
            (w, h) for w, h, _ratio, _label, is_custom, _hz in getattr(self, "_final_presets", []) if not is_custom
        }
        picks = [mode for mode in resolution.VALORANT_SAFE_RESOLUTIONS if mode in available]
        if customs and picks:
            modes_menu.addSeparator()
        for w, h in picks:
            act = modes_menu.addAction(f"{w} × {h}  ·  {resolution.get_aspect_ratio(w, h)}")
            act.triggered.connect(lambda _checked=False, cw=w, ch=h: self.change_res(cw, ch))
        if modes_menu.isEmpty():
            placeholder = modes_menu.addAction("Save modes in the app to list them here")
            placeholder.setEnabled(False)

        self.tray_menu.addSeparator()
        native_act = self.tray_menu.addAction(f"Restore Native\t{RESTORE_HOTKEY_TEXT}")
        native_act.triggered.connect(lambda: self.reset_res(enable_monitors=False))
        native_mon_act = self.tray_menu.addAction("Restore Native + Enable Monitors")
        native_mon_act.triggered.connect(lambda: self.reset_res(enable_monitors=True))
        self.tray_menu.addSeparator()
        quit_action = self.tray_menu.addAction("Quit EasyRes")
        quit_action.triggered.connect(self._quit_app)
