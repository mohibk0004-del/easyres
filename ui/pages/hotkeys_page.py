from PyQt6.QtWidgets import QComboBox

from ui.components.list_row import ListGroup, ListRow
from ui.controller import HOTKEY_MODIFIERS, RESTORE_HOTKEY_TEXT, VK_F1, mode_text
from ui.pages.base import Page
from ui.widgets import make_label, set_tone


class HotkeysPage(Page):
    title = "Hotkeys"
    subtitle = "Global shortcuts work while a game has focus. They change resolution only, never monitors."

    def __init__(self, controller, window, parent=None):
        super().__init__(controller, window, parent)
        c = controller

        toggle_group = ListGroup("Quick toggle")
        self.shortcut_row = ListRow("Shortcut", "")
        self.mod_combo = QComboBox()
        self.mod_combo.setAccessibleName("Hotkey modifier")
        for label, mods in HOTKEY_MODIFIERS:
            self.mod_combo.addItem(label, mods)
        self.key_combo = QComboBox()
        self.key_combo.setAccessibleName("Hotkey key")
        for n in range(1, 13):
            self.key_combo.addItem(f"F{n}", VK_F1 + n - 1)
        self.shortcut_row.add_trailing(self.mod_combo)
        self.shortcut_row.add_trailing(self.key_combo)
        toggle_group.add_row(self.shortcut_row)

        self.target_row = ListRow("Stretch target", "The mode the shortcut switches to from native.")
        self.target_combo = QComboBox()
        self.target_combo.setAccessibleName("Stretch target")
        self.target_combo.setMinimumWidth(220)
        self.target_row.add_trailing(self.target_combo)
        toggle_group.add_row(self.target_row)
        self.body_layout.addWidget(toggle_group)

        recovery = ListGroup("Recovery")
        self.restore_row = ListRow("Restore Native", "")
        self.restore_badge = make_label(RESTORE_HOTKEY_TEXT, role="badge")
        self.restore_row.add_trailing(self.restore_badge)
        recovery.add_row(self.restore_row)
        self.body_layout.addWidget(recovery)

        in_app = ListGroup("In the window")
        for keys, action in (("Ctrl+K", "Command palette"), ("Ctrl+F", "Search resolutions"),
                             ("Ctrl+1 … Ctrl+5", "Go to page"), ("Ctrl+Shift+R", "Restore Native")):
            row = ListRow(action)
            row.add_trailing(make_label(keys, role="badge"))
            in_app.add_row(row)
        self.body_layout.addWidget(in_app)
        self.finish()

        self.mod_combo.currentIndexChanged.connect(self._on_key_changed)
        self.key_combo.currentIndexChanged.connect(self._on_key_changed)
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        c.hotkey_changed.connect(self.sync)
        c.state_changed.connect(self._sync_targets)
        self.sync()

    def sync(self):
        c = self.controller
        name, vk, mods = c.hotkey_config()
        for combo, value in ((self.mod_combo, mods), (self.key_combo, vk)):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(value)))
            combo.blockSignals(False)
        if c.hotkey_registered:
            self.shortcut_row.set_subtitle(f"{name} is ready.")
        else:
            self.shortcut_row.set_subtitle(f"{name} is used by another app. Pick another key or add a modifier.", "warning")
        if c.restore_hotkey_registered:
            self.restore_row.set_subtitle("Works anywhere, even when EasyRes is in the tray.")
            set_tone(self.restore_badge, "accent")
        else:
            self.restore_row.set_subtitle("Unavailable: another app registered this shortcut.", "warning")
            set_tone(self.restore_badge, "warning")

    def _sync_targets(self):
        c = self.controller
        saved = c.hotkey_target()
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("Last stretched mode", None)
        selected = 0
        for preset in c.presets:
            prefix = f"{preset.label}  ·  " if preset.is_custom else ""
            self.target_combo.addItem(prefix + mode_text(preset.w, preset.h, preset.hz),
                                      {"w": preset.w, "h": preset.h, "hz": preset.hz})
            if saved and (saved["w"], saved["h"], saved["hz"]) == (preset.w, preset.h, preset.hz):
                selected = self.target_combo.count() - 1
        self.target_combo.setCurrentIndex(selected)
        self.target_combo.blockSignals(False)

    def _on_key_changed(self, _i=None):
        vk, mods = self.key_combo.currentData(), self.mod_combo.currentData()
        if isinstance(vk, int) and isinstance(mods, int):
            self.controller.set_hotkey(vk, mods)

    def _on_target_changed(self, _i=None):
        self.controller.set_hotkey_target(self.target_combo.currentData())
