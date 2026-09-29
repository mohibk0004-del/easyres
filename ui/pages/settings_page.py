import startup
import updater
from ui.components.list_row import ListGroup, ListRow
from ui.pages.base import Page
from ui.widgets import ActionButton, PremiumToggle
from ui.workers import run_async


class SettingsPage(Page):
    title = "Settings"

    def __init__(self, controller, window, parent=None):
        super().__init__(controller, window, parent)
        c = controller

        general = ListGroup("General")
        self._toggle(general, "Close button minimizes to tray", "minimize_to_tray", False)
        self._toggle(general, "Ask before closing", "ask_close", True)
        self.startup_row = ListRow("Start EasyRes at login",
                                   "" if startup.is_supported() else "Available in the packaged EasyRes.exe build.")
        self.startup_toggle = PremiumToggle("Start EasyRes at login")
        self.startup_toggle.setChecked(False, emit=False)
        self.startup_toggle.setEnabled(False)
        self.startup_toggle.toggled.connect(self._on_startup)
        self.startup_row.add_trailing(self.startup_toggle)
        general.add_row(self.startup_row)
        self._toggle(general, "Keep-or-revert prompt after switching", "ask_apply_res", True,
                     "Reverts automatically after 15 seconds unless you keep the new resolution.")
        self.body_layout.addWidget(general)

        updates = ListGroup("Updates")
        self.update_row = ListRow(f"EasyRes {updater.CURRENT_VERSION}", "")
        self.update_btn = ActionButton("Check for Updates")
        self.update_btn.clicked.connect(self._check)
        self.update_row.add_trailing(self.update_btn)
        updates.add_row(self.update_row)
        self.body_layout.addWidget(updates)

        more = ListGroup("More")
        hidden_row = ListRow("Hidden resolutions", "Bring back modes you hid from the Switch page.")
        hidden_btn = ActionButton("Show Hidden Modes")
        hidden_btn.clicked.connect(c.show_hidden_modes)
        hidden_row.add_trailing(hidden_btn)
        more.add_row(hidden_row)
        welcome_row = ListRow("Welcome guide", "The three-step introduction shown on first launch.")
        welcome_btn = ActionButton("Show Again")
        welcome_btn.clicked.connect(window.show_onboarding)
        welcome_row.add_trailing(welcome_btn)
        more.add_row(welcome_row)
        self.body_layout.addWidget(more)
        self.finish()

        c.update_changed.connect(self._sync_update)
        self._startup_loaded = False

    def _toggle(self, group, title, key, default, subtitle=""):
        row = ListRow(title, subtitle)
        toggle = PremiumToggle(title)
        toggle.setChecked(self.controller.setting_bool(key, default), emit=False)
        toggle.toggled.connect(lambda checked, k=key: self.controller.set_setting(k, checked))
        row.add_trailing(toggle)
        group.add_row(row)
        return toggle

    def on_shown(self):
        if startup.is_supported() and not self._startup_loaded:
            self._startup_loaded = True
            run_async(startup.is_enabled, on_done=self._startup_state, on_error=lambda _m: self._startup_state(False))
        self._sync_update()

    def _startup_state(self, enabled):
        self.startup_toggle.setChecked(bool(enabled), emit=False)
        self.startup_toggle.setEnabled(True)

    def _on_startup(self, enabled):
        self.startup_toggle.setEnabled(False)

        def done(result):
            ok, message = result
            self.startup_toggle.setEnabled(True)
            if ok:
                self.controller.set_setting("run_on_startup", enabled)
                self.startup_row.set_subtitle("Starts elevated at login via Task Scheduler." if enabled else "")
            else:
                self.startup_toggle.setChecked(not enabled, emit=False)
                self.startup_row.set_subtitle(f"Couldn't change it: {message}", "warning")

        run_async(startup.set_enabled, enabled, on_done=done, on_error=lambda m: done((False, m)))

    def _check(self):
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Checking…")

        def result(newer, latest, error):
            self.update_btn.setEnabled(True)
            self.update_btn.setText("Check for Updates")
            if error:
                self.update_row.set_subtitle(error, "warning")
            elif newer:
                self._sync_update()
                self.window_.prompt_update()
            else:
                self.update_row.set_subtitle("You're up to date.")

        self.controller.check_updates(on_result=result)

    def _sync_update(self):
        c = self.controller
        if c.update_status == "downloading":
            self.update_row.set_subtitle(f"Downloading {c.available_version()}… {c.update_percent}%")
            self.update_btn.setEnabled(False)
        elif c.update_status == "restarting":
            self.update_row.set_subtitle("Installing and restarting…")
            self.update_btn.setEnabled(False)
        elif c.available_release:
            self.update_row.set_subtitle(f"Version {c.available_version()} is available.")
            self.update_btn.setText("Install Update")
            self.update_btn.setEnabled(True)
            try:
                self.update_btn.clicked.disconnect()
            except TypeError:
                pass
            self.update_btn.clicked.connect(self.window_.prompt_update)
