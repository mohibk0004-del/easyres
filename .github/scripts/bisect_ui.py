"""Show each UI piece in its own process to find which one crashes.

Usage: python bisect_ui.py            -> runs every step in a subprocess
       python bisect_ui.py <step>     -> runs one step
"""
import faulthandler
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
faulthandler.enable()

STEPS = [
    "plain", "styled", "toggle", "action_button", "icon_button", "status_item", "mode_tile",
    "sidebar", "segmented", "toast", "list_group", "sheet_host",
    "page_switch", "page_custom", "page_monitors", "page_hotkeys", "page_settings", "app_window",
    "aw_no_native_event", "aw_no_tray", "aw_no_event_filter", "aw_no_hotkeys", "aw_no_frameless",
    "aw_no_shortcuts", "aw_all_off",
]

AW_PATCHES = {
    "aw_no_native_event": ["native_event"],
    "aw_no_tray": ["tray"],
    "aw_no_event_filter": ["event_filter"],
    "aw_no_hotkeys": ["hotkeys"],
    "aw_no_frameless": ["frameless"],
    "aw_no_shortcuts": ["shortcuts"],
    "aw_all_off": ["native_event", "tray", "event_filter", "hotkeys", "frameless", "shortcuts"],
}


def patch_app_window(features):
    import ui.app_window as aw
    from PyQt6.QtWidgets import QApplication, QMainWindow
    if "native_event" in features:
        aw.NO_NATIVE_EVENT = True
    if "tray" in features:
        class FakeTray:
            def showMessage(self, *a, **k):
                pass

            def hide(self):
                pass

            def setIcon(self, *a):
                pass

        def build_tray(self):
            self.tray_icon = FakeTray()
            from PyQt6.QtWidgets import QMenu
            self.tray_menu = QMenu()
        aw.AppWindow._build_tray = build_tray
        aw.AppWindow._set_tray_icon = lambda self: None
    if "event_filter" in features:
        QApplication.installNativeEventFilter = lambda self, f: None
    if "hotkeys" in features:
        from ui.controller import AppController
        AppController.register_hotkeys = lambda self: None
    if "frameless" in features:
        original = QMainWindow.setWindowFlags

        def set_flags(self, flags):
            return original(self, aw.Qt.WindowType.Window)
        aw.AppWindow.setWindowFlags = set_flags
    if "shortcuts" in features:
        class NoShortcut:
            def __init__(self, *a, **k):
                from PyQt6.QtCore import QObject, pyqtSignal

                class S(QObject):
                    activated = pyqtSignal()
                self._s = S()
                self.activated = self._s.activated
        aw.QShortcut = NoShortcut


def run_step(step):
    # If the step hangs, dump every thread's stack and exit.
    faulthandler.dump_traceback_later(40, exit=True)
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
    app = QApplication(sys.argv)
    if step != "plain":
        from theme import styles
        styles.apply_app_style(app)

    host = QWidget()
    layout = QVBoxLayout(host)
    controller = None

    def make_controller():
        from ui.controller import AppController
        return AppController()

    if step == "toggle":
        from ui.widgets import PremiumToggle
        layout.addWidget(PremiumToggle("t"))
    elif step == "action_button":
        from ui.widgets import ActionButton
        layout.addWidget(ActionButton("Go", primary=True))
    elif step == "icon_button":
        from ui.widgets import IconButton
        layout.addWidget(IconButton("settings", "Settings", "Settings"))
    elif step == "status_item":
        from ui.widgets import StatusItem
        item = StatusItem("Current", "1920 × 1080")
        layout.addWidget(item)
    elif step == "mode_tile":
        from ui.widgets import ModeTile
        layout.addWidget(ModeTile(1920, 1080, "16:9", "", rates=[144, 60]))
    elif step == "sidebar":
        from ui.components.sidebar import Sidebar
        sidebar = Sidebar()
        sidebar.add_item("switch", "Switch")
        sidebar.add_item("settings", "Settings", bottom=True)
        sidebar.set_current(0, animate=False)
        layout.addWidget(sidebar)
    elif step == "segmented":
        from ui.components.segmented import SegmentedControl
        layout.addWidget(SegmentedControl(["All", "16:9", "4:3"]))
    elif step == "toast":
        from ui.components.toast import Toast
        toast = Toast()
        layout.addWidget(toast)
        toast.show_message("Hello")
    elif step == "list_group":
        from ui.components.list_row import ListGroup, ListRow
        group = ListGroup("Group")
        group.add_row(ListRow("Row", "Sub"))
        group.add_row(ListRow("Row 2"))
        layout.addWidget(group)
    elif step == "sheet_host":
        from ui.widgets import make_label
        layout.addWidget(make_label("label", role="page-title"))
    elif step.startswith("page_"):
        controller = make_controller()
        controller.refresh()

        class FakeWindow:
            def confirm(self, *a, **k):
                return False

            def show_onboarding(self):
                pass

            def prompt_update(self):
                pass

        name = step[len("page_"):]
        module = __import__(f"ui.pages.{name}_page", fromlist=["x"])
        cls = {"switch": "SwitchPage", "custom": "CustomPage", "monitors": "MonitorsPage",
               "hotkeys": "HotkeysPage", "settings": "SettingsPage"}[name]
        layout.addWidget(getattr(module, cls)(controller, FakeWindow()))
    elif step == "app_window" or step in AW_PATCHES:
        patch_app_window(AW_PATCHES.get(step, []))
        from ui.app_window import AppWindow
        host = AppWindow()

    print(f"{step}: showing", flush=True)
    host.resize(900, 600)
    host.show()
    print(f"{step}: shown", flush=True)
    ticks = []

    def tick():
        ticks.append(1)
        print(f"{step}: event loop tick {len(ticks)}", flush=True)

    heartbeat = QTimer()
    heartbeat.timeout.connect(tick)
    heartbeat.start(500)
    QTimer.singleShot(1500, app.quit)
    app.exec()
    print(f"{step}: OK", flush=True)
    os._exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_step(sys.argv[1])
    else:
        failures = []
        for step in STEPS:
            result = subprocess.run([sys.executable, __file__, step], capture_output=True, text=True, timeout=120)
            ok = result.returncode == 0 and f"{step}: OK" in result.stdout
            print(f"==== {step}: {'PASS' if ok else 'FAIL (exit %s)' % result.returncode}", flush=True)
            if not ok:
                failures.append(step)
                print(result.stdout[-3000:], result.stderr[-3000:], flush=True)
        print("FAILED STEPS:", failures or "none", flush=True)
