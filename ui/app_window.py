"""EasyRes main window: sidebar + pages, status strip, recovery bar.

State and actions live in ui.controller.AppController; this module is view
code, window chrome, sheets, tray and shortcuts.
"""

import os
from ctypes import wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QAbstractButton, QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSizeGrip, QStackedWidget,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

import updater
from theme import styles
from theme import tokens as t
from theme.assets import asset_base_path
from theme.motion import duration
from ui import motion, native_chrome
from ui.components.sheet import Sheet
from ui.components.sidebar import Sidebar
from ui.components.toast import Toast
from ui.controller import (
    HOTKEY_ID_RESTORE, HOTKEY_ID_TOGGLE, RESTORE_HOTKEY_TEXT, AppController, mode_text,
)
from ui.dialogs import RevertDialog, StandardButton, themed_message_box
from ui.pages.custom_page import CustomPage
from ui.pages.hotkeys_page import HotkeysPage
from ui.pages.monitors_page import MonitorsPage
from ui.pages.settings_page import SettingsPage
from ui.pages.switch_page import SwitchPage
from ui.widgets import ActionButton, IconButton, StatusItem, make_label

WM_HOTKEY = 0x0312
NO_NATIVE_EVENT = bool(os.environ.get("EASYRES_NO_NATIVE_EVENT"))


def trace(message):
    """Startup breadcrumbs for diagnosing crashes (EASYRES_TRACE=1)."""
    if os.environ.get("EASYRES_TRACE"):
        print(f"[trace] {message}", flush=True)


PAGE_SWITCH, PAGE_CUSTOM, PAGE_MONITORS, PAGE_HOTKEYS, PAGE_SETTINGS = range(5)


class HotkeyEventFilter(QAbstractNativeEventFilter):
    """Global hotkeys arrive as thread messages (no window), so they are
    caught at the application level."""

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


class ChromeEventFilter(QAbstractNativeEventFilter):
    """Routes the main window's Win32 messages to ui.native_chrome.

    Messages are ignored until attach() is given the window handle after the
    first show, so nothing runs during native window creation.
    """

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.hwnd = None

    def attach(self, hwnd):
        self.hwnd = hwnd

    def nativeEventFilter(self, eventType, message):
        if self.hwnd is None:
            return False, 0
        event_type = eventType.encode() if isinstance(eventType, str) else bytes(eventType)
        if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.hWnd is None or int(msg.hWnd) != self.hwnd:
            return False, 0
        return native_chrome.handle_msg(self.window, msg)


class TransitionOverlay(QWidget):
    """Cross-fades page snapshots: old fades out, new fades in rising 8px."""

    RISE = 8

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.old = None
        self.new = None
        self.p = 1.0
        self.anim = None
        self.hide()

    def run(self, old, new, on_done):
        self.old, self.new, self.p = old, new, 0.0
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        motion.stop(self.anim)

        def finished():
            self.hide()
            self.old = self.new = None
            on_done()

        self.anim = motion.tween(self, 0.0, 1.0, t.MOTION_PAGE, self._set, on_finished=finished)

    def _set(self, value):
        self.p = float(value)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(t.BG_BASE))
        if self.old is not None:
            p.setOpacity(1.0 - self.p)
            p.drawPixmap(QPointF(0, 0), self.old)
        if self.new is not None:
            p.setOpacity(self.p)
            p.drawPixmap(QPointF(0, self.RISE * (1.0 - self.p)), self.new)


class ProgressBody(QWidget):
    """Step list for long operations (EDID injection)."""

    def __init__(self, steps):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_SM)
        self.rows = []
        for step in steps:
            row = QHBoxLayout()
            mark = make_label("○", role="muted")
            mark.setFixedWidth(18)
            text = make_label(step, role="muted")
            row.addWidget(mark)
            row.addWidget(text, 1)
            layout.addLayout(row)
            self.rows.append((mark, text))

    def set_step(self, index):
        for i, (mark, text) in enumerate(self.rows):
            if i < index:
                mark.setText("✓")
                styles.set_props(text, role="body")
            elif i == index:
                mark.setText("●")
                styles.set_props(text, role="strong")
            else:
                mark.setText("○")
                styles.set_props(text, role="muted")


class ProgressSheet:
    def __init__(self, host, title, steps):
        self.body = ProgressBody(steps)
        self.steps = steps
        self.sheet = Sheet(host, title, "Keep EasyRes open. Your screen will flash while the driver restarts.",
                           body_widget=self.body, dismissible=False)
        # Callers usually drop their reference; the sheet keeps this helper
        # (and its signal connection) alive until it closes.
        self.sheet.progress_helper = self
        self.sheet.open()
        self._signal = None

    def bind(self, signal):
        self._signal = signal
        signal.connect(self._on_step)

    def _on_step(self, index):
        if index < 0 or index >= len(self.steps):
            try:
                self._signal.disconnect(self._on_step)
            except (TypeError, RuntimeError):
                pass
            self.sheet.close_with(index >= 0)
            return
        self.body.set_step(index)


class AppWindow(QMainWindow):
    def __init__(self, controller=None):
        super().__init__()
        self.setWindowTitle("EasyRes")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setMinimumSize(t.WINDOW_MIN_WIDTH, t.WINDOW_MIN_HEIGHT)
        self._fit_initial_size()
        app = QApplication.instance()
        styles.apply_app_style(app)

        self.native_chrome = False
        self._quitting = False
        self._shown_once = False
        self._busy_cursor = False
        self._revert_sheet = None
        self._revert_dialog = None
        self.controller = controller or AppController()
        c = self.controller

        self._build()
        self._build_tray()
        self._connect()

        self.hotkey_filter = HotkeyEventFilter({
            HOTKEY_ID_TOGGLE: c.toggle_stretch_native,
            HOTKEY_ID_RESTORE: lambda: c.reset_res(enable_monitors=False),
        })
        app.installNativeEventFilter(self.hotkey_filter)
        self.chrome_filter = ChromeEventFilter(self)
        app.installNativeEventFilter(self.chrome_filter)
        # Windows sign-out / shutdown: never block it with the close prompt.
        app.commitDataRequest.connect(self._on_session_end)
        c.register_hotkeys()
        c.refresh()
        c.refresh_monitors()
        c.check_updates()
        QTimer.singleShot(400, self._maybe_onboard)
        trace("AppWindow.__init__: done")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _fit_initial_size(self):
        screen = QApplication.primaryScreen()
        width, height = 1080, 720
        if screen:
            available = screen.availableGeometry()
            width = max(t.WINDOW_MIN_WIDTH, min(width, available.width() - 80))
            height = max(t.WINDOW_MIN_HEIGHT, min(height, available.height() - 60))
        self.resize(width, height)

    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(root)
        self.root = root
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        head = QHBoxLayout(self.sidebar.header)
        head.setContentsMargins(t.SPACE_SM, 0, 0, 0)
        head.setSpacing(t.SPACE_SM)
        logo = QLabel()
        logo.setFixedSize(20, 20)
        icon_file = os.path.join(asset_base_path(), "icon.png")
        if os.path.exists(icon_file):
            pixmap = QPixmap(icon_file).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(3)
            logo.setPixmap(pixmap)
        self.app_title = make_label("EasyRes", role="app-title")
        head.addWidget(logo)
        head.addWidget(self.app_title)
        head.addStretch()
        for icon, text in (("switch", "Switch"), ("custom", "Custom"), ("monitor", "Monitors"), ("keyboard", "Hotkeys")):
            self.sidebar.add_item(icon, text)
        self.sidebar.add_item("settings", "Settings", bottom=True)
        layout.addWidget(self.sidebar)

        # Main column
        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        layout.addWidget(main, 1)

        self.header = QWidget()
        self.header.setObjectName("Header")
        self.header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.header.setFixedHeight(t.HEADER_H)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(t.SPACE_2XL, 0, t.SPACE_SM, 0)
        header_layout.setSpacing(t.SPACE_XL)
        self.stat_resolution = StatusItem("Current")
        self.stat_refresh = StatusItem("Refresh")
        self.stat_mode = StatusItem("Mode")
        self.stat_monitors = StatusItem("Monitors")
        for item in (self.stat_resolution, self.stat_refresh, self.stat_mode, self.stat_monitors):
            header_layout.addWidget(item)
        header_layout.addStretch()
        self.update_btn = QPushButton()
        self.update_btn.setProperty("variant", "pill")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.update_btn.clicked.connect(self.prompt_update)
        self.update_btn.hide()
        header_layout.addWidget(self.update_btn)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        self.min_btn = IconButton("minimize", "Minimize", "Minimize")
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn = IconButton("maximize", "Maximize", "Maximize")
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn = IconButton("close", "Close", "Close", danger=True)
        self.close_btn.clicked.connect(self.close)
        for button in (self.min_btn, self.max_btn, self.close_btn):
            buttons.addWidget(button)
        header_layout.addLayout(buttons)
        main_layout.addWidget(self.header)

        self.stack = QStackedWidget()
        c = self.controller
        self.pages = [
            SwitchPage(c, self), CustomPage(c, self), MonitorsPage(c, self), HotkeysPage(c, self), SettingsPage(c, self),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        main_layout.addWidget(self.stack, 1)
        self.transition = TransitionOverlay(self.stack)

        bar = QWidget()
        bar.setObjectName("ActionBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(t.SPACE_2XL, t.SPACE_MD, t.SPACE_LG, t.SPACE_MD)
        bar_layout.setSpacing(t.SPACE_MD)
        self.toast = Toast()
        self.reset_btn = ActionButton("Restore Native")
        self.reset_btn.setToolTip(f"Restore the native resolution. Monitors are not changed. ({RESTORE_HOTKEY_TEXT} anywhere)")
        self.reset_btn.clicked.connect(lambda: c.reset_res(enable_monitors=False))
        self.reset_mon_btn = ActionButton("Restore Native + Enable Monitors", destructive=True)
        self.reset_mon_btn.setToolTip("Restore the native resolution and turn every monitor device back on")
        self.reset_mon_btn.clicked.connect(lambda: c.reset_res(enable_monitors=True))
        bar_layout.addWidget(self.toast, 1)
        bar_layout.addWidget(self.reset_btn)
        bar_layout.addWidget(self.reset_mon_btn)
        main_layout.addWidget(bar)

        self.grip = QSizeGrip(root)
        self.grip.resize(14, 14)
        self.grip.hide()

        self.sidebar.current_changed.connect(self.show_page)
        self.sidebar.set_current(PAGE_SWITCH, animate=False)
        self.pages[PAGE_SWITCH].open_hotkeys.connect(lambda: self.sidebar.set_current(PAGE_HOTKEYS))

        for index in range(5):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(lambda i=index: self._guarded(lambda: self.sidebar.set_current(i)))
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(lambda: self._guarded(self.show_palette))
        QShortcut(QKeySequence.StandardKey.Find, self).activated.connect(lambda: self._guarded(self._focus_search))
        QShortcut(QKeySequence("Ctrl+Shift+R"), self).activated.connect(lambda: c.reset_res(enable_monitors=False))

        for drag_area in (self.header, self.sidebar.header):
            drag_area.installEventFilter(self)

    def _connect(self):
        c = self.controller
        c.state_changed.connect(self._sync_status)
        c.notify.connect(self._on_notify)
        c.busy_changed.connect(self._on_busy)
        c.update_changed.connect(self._sync_update)
        c.revert_requested.connect(self._on_revert_requested)
        c.revert_cancelled.connect(self._on_revert_cancelled)
        c.hotkey_changed.connect(self.update_tray_menu)
        c.state_changed.connect(self.update_tray_menu)

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    def show_page(self, index):
        if index == self.stack.currentIndex():
            return
        old = self.stack.currentWidget().grab() if self.stack.isVisible() else None
        self.stack.setCurrentIndex(index)
        page = self.pages[index]
        page.on_shown()
        if old is not None and duration(t.MOTION_PAGE):
            self.transition.run(old, page.grab(), lambda: None)

    def _focus_search(self):
        self.sidebar.set_current(PAGE_SWITCH)
        self.pages[PAGE_SWITCH].focus_search()

    def _guarded(self, fn):
        if not self._sheet_open():
            fn()

    def _sheet_open(self):
        return any(sheet.isVisible() for sheet in self.root.findChildren(Sheet))

    # ------------------------------------------------------------------
    # Status, feedback
    # ------------------------------------------------------------------
    def _sync_status(self):
        s = self.controller.status()
        self.stat_resolution.set_value(s["resolution"], s["resolution_tone"])
        self.stat_refresh.set_value(s["refresh"])
        self.stat_mode.set_value(s["mode"], s["mode_tone"])
        self.stat_monitors.set_value(s["monitors"], s["monitors_tone"])

    def _on_notify(self, text, tone, ms):
        self.toast.show_message(text, tone, ms)
        if tone == "warning" and not self.isVisible():
            self.tray_icon.showMessage("EasyRes", text, QSystemTrayIcon.MessageIcon.Warning, 4000)

    def _on_busy(self, busy):
        if busy and not self._busy_cursor:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
            self._busy_cursor = True
        elif not busy and self._busy_cursor:
            QApplication.restoreOverrideCursor()
            self._busy_cursor = False

    def sheet_host(self):
        return self.root

    def confirm(self, title, text, action_label, destructive=False):
        reply = themed_message_box(
            self, title, text,
            QMessageBox.Icon.Warning if destructive else QMessageBox.Icon.Question,
            StandardButton.Yes | StandardButton.Cancel,
            labels={StandardButton.Yes: action_label},
        )
        return reply == StandardButton.Yes

    def progress_sheet(self, title, steps):
        return ProgressSheet(self.sheet_host(), title, steps)

    # ------------------------------------------------------------------
    # Keep / revert
    # ------------------------------------------------------------------
    def _on_revert_requested(self, text, previous):
        c = self.controller
        if self.isVisible() and not self.isMinimized():
            remaining = [t.REVERT_SECONDS]

            def message():
                return f"Switched to {text}. Reverting in {remaining[0]} s unless you keep it."

            sheet = Sheet(self.sheet_host(), "Keep this resolution?", message(),
                          [("Revert", False, "secondary"), ("Keep", True, "primary")], cancel_value=False)
            timer = QTimer(sheet)
            timer.setInterval(1000)

            def tick():
                remaining[0] -= 1
                if remaining[0] <= 0:
                    timer.stop()
                    sheet.close_with(False)
                else:
                    sheet.set_text(message())

            def finished(keep):
                timer.stop()
                self._revert_sheet = None
                if keep is None:
                    return  # Cancelled by Restore Native.
                if keep:
                    c.keep_mode()
                else:
                    c.revert_to(previous)

            timer.timeout.connect(tick)
            sheet.finished.connect(finished)
            self._revert_sheet = sheet
            sheet.open()
            timer.start()
            return

        dialog = RevertDialog(text)
        self._revert_dialog = dialog
        dialog.exec()
        self._revert_dialog = None
        if getattr(dialog, "cancelled", False):
            return
        if dialog.keep:
            c.keep_mode()
        else:
            c.revert_to(previous)

    def _on_revert_cancelled(self):
        if self._revert_sheet is not None:
            self._revert_sheet.close_with(None)
        if self._revert_dialog is not None:
            self._revert_dialog.cancelled = True
            self._revert_dialog.reject()

    # ------------------------------------------------------------------
    # Onboarding and command palette
    # ------------------------------------------------------------------
    def _maybe_onboard(self):
        if not self.controller.setting_bool("tutorial_shown", False):
            self.controller.set_setting("tutorial_shown", True)
            self.show_onboarding()

    def show_onboarding(self):
        name, _vk, _mods = self.controller.hotkey_config()
        cards = (
            ("Switch in one click",
             "Set your game to Windowed Fullscreen, then pick a resolution on the Switch page. "
             "You get 15 seconds to keep it, or it reverts on its own."),
            ("Toggle from the game",
             f"{name} flips between native and your stretch target without leaving the game. "
             "Choose the target on the Hotkeys page."),
            ("Always a way back",
             f"Restore Native ({RESTORE_HOTKEY_TEXT}, works anywhere) brings back your normal resolution. "
             "On laptops, true stretch may need the built-in panel turned off on the Monitors page. "
             "Black bars? Set GPU scaling to Full Screen and use Fill in-game."),
        )
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_MD)
        pages = QStackedWidget()
        for title, text in cards:
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(t.SPACE_SM)
            card_layout.addWidget(make_label(title, role="strong"))
            card_layout.addWidget(make_label(text, role="muted", wrap=True))
            card_layout.addStretch()
            pages.addWidget(card)
        layout.addWidget(pages)
        nav = QHBoxLayout()
        dots = make_label("", role="caption")
        back = ActionButton("Back")
        next_btn = ActionButton("Next", primary=True)
        next_btn.setDefault(True)
        nav.addWidget(dots)
        nav.addStretch()
        nav.addWidget(back)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        sheet = Sheet(self.sheet_host(), "Welcome to EasyRes", body_widget=body)

        def sync():
            i = pages.currentIndex()
            dots.setText("  ".join("●" if n == i else "○" for n in range(pages.count())))
            back.setEnabled(i > 0)
            next_btn.setText("Get Started" if i == pages.count() - 1 else "Next")

        def go(step):
            i = pages.currentIndex() + step
            if i >= pages.count():
                sheet.close_with(True)
                return
            pages.setCurrentIndex(max(0, i))
            sync()

        back.clicked.connect(lambda: go(-1))
        next_btn.clicked.connect(lambda: go(1))
        sync()
        sheet.open()

    def palette_commands(self):
        c = self.controller
        commands = [
            ("Restore Native", "", lambda: c.reset_res(enable_monitors=False)),
            ("Restore Native + Enable Monitors", "", lambda: c.reset_res(enable_monitors=True)),
            ("Toggle Stretch / Native", c.hotkey_config()[0], c.toggle_stretch_native),
        ]
        for index, name in enumerate(("Switch", "Custom Resolution", "Monitors", "Hotkeys", "Settings")):
            commands.append((f"Go to {name}", f"Ctrl+{index + 1}", lambda i=index: self.sidebar.set_current(i)))
        for preset in c.presets:
            label = f"Apply {mode_text(preset.w, preset.h, preset.hz)}"
            detail = preset.label if preset.is_custom else preset.group
            commands.append((label, detail, lambda p=preset: c.change_res(p.w, p.h, p.hz)))
        return commands

    def show_palette(self):
        commands = self.palette_commands()
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_SM)
        field = QLineEdit()
        field.setPlaceholderText("Type a command or resolution…")
        field.setAccessibleName("Command")
        results = QListWidget()
        results.setObjectName("Palette")
        results.setAccessibleName("Results")
        results.setFixedHeight(260)
        results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(field)
        layout.addWidget(results)
        sheet = Sheet(self.sheet_host(), "Command", body_widget=body, width=520)

        def refill(text=""):
            results.clear()
            parts = text.lower().split()
            for label, detail, action in commands:
                hay = f"{label} {detail}".lower()
                if all(part in hay for part in parts):
                    item = QListWidgetItem(f"{label}    {detail}" if detail else label)
                    item.setData(Qt.ItemDataRole.UserRole, action)
                    results.addItem(item)
            results.setCurrentRow(0)

        def run(item=None):
            item = item or results.currentItem()
            if item is None:
                return
            action = item.data(Qt.ItemDataRole.UserRole)
            sheet.close_with(True)
            QTimer.singleShot(0, action)

        def keys(event, original=field.keyPressEvent):
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = results.currentRow() + (1 if event.key() == Qt.Key.Key_Down else -1)
                results.setCurrentRow(max(0, min(results.count() - 1, row)))
                return
            original(event)

        field.keyPressEvent = keys
        field.textChanged.connect(refill)
        field.returnPressed.connect(run)
        results.itemClicked.connect(run)
        refill()
        sheet.open()
        QTimer.singleShot(t.MOTION_SHEET_IN + 20, lambda: field.setFocus(Qt.FocusReason.PopupFocusReason))

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------
    def _sync_update(self):
        c = self.controller
        if c.update_status == "downloading":
            self.update_btn.setText(f"Downloading {c.update_percent}%")
            self.update_btn.setEnabled(False)
        elif c.update_status == "restarting":
            self.update_btn.setText("Restarting…")
            self.update_btn.setEnabled(False)
        elif c.available_release:
            version = c.available_version()
            self.update_btn.setText(f"Update to {version}")
            self.update_btn.setAccessibleName(f"Update EasyRes to version {version}")
            self.update_btn.setEnabled(True)
        self.update_btn.setVisible(bool(c.available_release))
        self.sidebar.items[PAGE_SETTINGS].badge = bool(c.available_release) and not c.update_status
        self.sidebar.items[PAGE_SETTINGS].update()
        self._set_tray_icon()

    def prompt_update(self):
        c = self.controller
        if not c.available_release or c.update_status:
            return
        version = c.available_version()
        if not updater.can_self_update():
            themed_message_box(self, f"EasyRes {version} is available",
                               "Automatic updates work in the packaged EasyRes.exe build. "
                               "Download the new version from the GitHub release page.")
            return
        try:
            asset = updater.select_windows_asset(c.available_release)
        except updater.UpdateError as exc:
            c.notify.emit(str(exc), "warning", 6000)
            return
        size_mb = (int(asset.get("size") or 0)) / (1024 * 1024)
        if self.confirm(f"Install EasyRes {version}?",
                        f"The update is {size_mb:.1f} MB. EasyRes downloads and verifies it, then closes, "
                        "replaces itself, and restarts. If anything fails, your current version is kept.",
                        "Install and Restart"):
            c.start_update(on_ready=self._quit_app)

    # ------------------------------------------------------------------
    # Tray
    # ------------------------------------------------------------------
    def _build_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("EasyRes")
        self.tray_menu = QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self._set_tray_icon()
        self.tray_icon.show()

    def _set_tray_icon(self):
        icon_file = os.path.join(asset_base_path(), "icon.png")
        if not os.path.exists(icon_file):
            return
        pixmap = QPixmap(icon_file).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        if self.controller.available_release:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.ACCENT_PRIMARY))
            painter.drawEllipse(QRectF(40, 0, 24, 24))
            painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def update_tray_menu(self):
        c = self.controller
        menu = self.tray_menu
        menu.clear()
        menu.addAction("Open EasyRes").triggered.connect(
            lambda: self._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger))
        menu.addAction(f"Toggle Stretch / Native\t{c.hotkey_config()[0]}").triggered.connect(c.toggle_stretch_native)
        menu.addSeparator()
        modes = menu.addMenu("Switch Resolution")
        customs = [p for p in c.presets if p.is_custom]
        for p in customs:
            modes.addAction(f"{p.label}  ({mode_text(p.w, p.h, p.hz)})").triggered.connect(
                lambda _c=False, p=p: c.change_res(p.w, p.h, p.hz))
        available = {(p.w, p.h) for p in c.presets if not p.is_custom}
        import resolution
        picks = [m for m in resolution.VALORANT_SAFE_RESOLUTIONS if m in available]
        if customs and picks:
            modes.addSeparator()
        for w, h in picks:
            modes.addAction(f"{w} × {h}  ·  {resolution.get_aspect_ratio(w, h)}").triggered.connect(
                lambda _c=False, w=w, h=h: c.change_res(w, h))
        if modes.isEmpty():
            modes.addAction("Save modes in the app to list them here").setEnabled(False)
        menu.addSeparator()
        menu.addAction(f"Restore Native\t{RESTORE_HOTKEY_TEXT}").triggered.connect(
            lambda: c.reset_res(enable_monitors=False))
        menu.addAction("Restore Native + Enable Monitors").triggered.connect(lambda: c.reset_res(enable_monitors=True))
        if c.available_release:
            menu.addSeparator()
            menu.addAction(f"Update to {c.available_version()}…").triggered.connect(self._open_and_update)
        menu.addSeparator()
        menu.addAction("Quit EasyRes").triggered.connect(self._quit_app)

    def _open_and_update(self):
        self._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
        QTimer.singleShot(0, self.prompt_update)

    # ------------------------------------------------------------------
    # Window chrome
    # ------------------------------------------------------------------
    def showEvent(self, event):
        trace("showEvent: begin")
        super().showEvent(event)
        if self._shown_once:
            return
        self._shown_once = True
        trace("showEvent: installing native chrome")
        self.native_chrome = native_chrome.install(self, t.BORDER_SUBTLE)
        trace(f"showEvent: native chrome = {self.native_chrome}")
        if not NO_NATIVE_EVENT:
            self.chrome_filter.attach(int(self.winId()))
        self.grip.setVisible(not self.native_chrome)
        self.root.setFocus(Qt.FocusReason.OtherFocusReason)
        self._sync_status()
        if duration(t.MOTION_FADE) and not os.environ.get("EASYRES_NO_FADE"):
            self.setWindowOpacity(0.0)
            self._fade = motion.tween(self, 0.0, 1.0, t.MOTION_FADE, self.setWindowOpacity)
        trace("showEvent: end")

    # Note: never override QWidget.nativeEvent here. With PyQt6 on Windows the
    # override itself crashes (access violation) during the first show; window
    # messages are handled by ChromeEventFilter at the application level.

    def resize_border(self):
        return t.RESIZE_BORDER

    def native_hit_test(self, pos):
        max_rect = self.max_btn.rect().translated(self.max_btn.mapTo(self, self.max_btn.rect().topLeft()))
        if max_rect.contains(pos):
            return "max"
        in_header = (self.header.geometry().contains(self.header.parentWidget().mapFrom(self, pos))
                     or self.sidebar.header.rect().contains(self.sidebar.header.mapFrom(self, pos)))
        if not in_header or self._sheet_open():
            return "client"
        widget = self.childAt(pos)
        interactive = (QAbstractButton, QComboBox, QLineEdit)
        while widget is not None and widget is not self:
            if isinstance(widget, interactive):
                return "client"
            widget = widget.parentWidget()
        return "caption"

    def set_max_hover(self, hover):
        if bool(self.max_btn.property("hover")) != hover:
            styles.set_props(self.max_btn, hover=hover)

    def press_max(self):
        self.toggle_maximize()

    def on_display_change(self):
        self.controller.schedule_refresh()

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            maximized = self.isMaximized()
            self.max_btn.set_icon_name("restore" if maximized else "maximize")
            self.max_btn.setToolTip("Restore" if maximized else "Maximize")
            self.max_btn.setAccessibleName(self.max_btn.toolTip())
            self.grip.setVisible(not self.native_chrome and not maximized)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sidebar.set_rail(self.width() < t.SIDEBAR_RAIL_BREAKPOINT)
        self.app_title.setVisible(self.width() >= t.SIDEBAR_RAIL_BREAKPOINT)
        self.grip.move(self.root.width() - self.grip.width(), self.root.height() - self.grip.height())
        self.transition.setGeometry(self.stack.rect())

    def eventFilter(self, obj, event):
        # Qt-only fallback for moving the window when native chrome is off.
        if not self.native_chrome and obj in (self.header, self.sidebar.header):
            if event.type() == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemMove()
                return True
            if event.type() == event.Type.MouseButtonDblClick:
                self.toggle_maximize()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Close / quit
    # ------------------------------------------------------------------
    def _on_session_end(self, _manager=None):
        self._quitting = True
        self.controller.unregister_hotkeys()

    def _quit_app(self):
        self._quitting = True
        self.controller.unregister_hotkeys()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        c = self.controller
        if not c.setting_bool("ask_close", True):
            if c.setting_bool("minimize_to_tray", False):
                event.ignore()
                self.hide()
                self._tray_hint_once()
            else:
                event.accept()
                self._quit_app()
            return
        event.ignore()
        QTimer.singleShot(0, self._ask_close)

    def _ask_close(self):
        c = self.controller
        reply, remember = themed_message_box(
            self, "Keep EasyRes running?",
            "In the tray, the quick toggle and Restore Native hotkeys keep working.",
            QMessageBox.Icon.Question,
            StandardButton.Yes | StandardButton.No | StandardButton.Cancel,
            "Remember my choice",
            labels={StandardButton.Yes: "Minimize to Tray", StandardButton.No: "Quit"},
        )
        if reply == StandardButton.Yes:
            if remember:
                c.set_setting("minimize_to_tray", True)
                c.set_setting("ask_close", False)
            self.hide()
            self._tray_hint_once()
        elif reply == StandardButton.No:
            if remember:
                c.set_setting("minimize_to_tray", False)
                c.set_setting("ask_close", False)
            self._quit_app()

    def _tray_hint_once(self):
        c = self.controller
        if not c.setting_bool("tray_hint_shown", False):
            c.set_setting("tray_hint_shown", True)
            self.tray_icon.showMessage("EasyRes is still running", "Right-click the tray icon for quick switching.",
                                       QSystemTrayIcon.MessageIcon.Information, 4000)
