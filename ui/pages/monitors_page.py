from ui.components.list_row import ListGroup, ListRow
from ui.controller import monitor_is_on
from ui.pages.base import Page
from ui.widgets import PremiumToggle, make_label


class MonitorsPage(Page):
    title = "Monitors"
    subtitle = ("Turn monitor devices on or off. On many laptops, turning the built-in panel's device off "
                "lets the GPU stretch the image. Resolution changes and hotkeys never touch these.")

    def __init__(self, controller, window, parent=None):
        super().__init__(controller, window, parent)
        self.group = ListGroup("Monitor devices")
        self.body_layout.addWidget(self.group)
        self.body_layout.addWidget(make_label(
            "Restore Native + Enable Monitors (bottom bar or tray) turns every device back on.",
            role="caption", wrap=True))
        self.finish()
        controller.monitors_changed.connect(self.sync)
        self.sync()

    def on_shown(self):
        self.controller.refresh_monitors()

    def sync(self):
        c = self.controller
        self.group.clear()
        if not c.hw_loaded:
            self.group.add_row(ListRow("Detecting monitors…"))
            return
        if not c.hw_monitors:
            self.group.add_row(ListRow("No monitor devices found", "Windows didn't report any connected monitor devices."))
            return
        for monitor in c.hw_monitors:
            instance_id = monitor.get("Instance ID", "")
            description = monitor.get("Device Description") or "Unknown monitor"
            on = monitor_is_on(monitor)
            pending = instance_id in c.monitor_pending
            row = ListRow(description)
            row.setToolTip(instance_id)
            if pending:
                row.set_subtitle("Working…")
            else:
                row.set_subtitle("On" if on else "Off", None if on else "warning")
            toggle = PremiumToggle(f"{description} power")
            toggle.setChecked(on, emit=False)
            toggle.setEnabled(not pending)
            toggle.toggled.connect(lambda checked, iid=instance_id, desc=description:
                                   c.set_monitor_power(iid, checked, desc))
            row.add_trailing(toggle)
            self.group.add_row(row)
