from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from theme import tokens as t
from ui.components.segmented import SegmentedControl
from ui.controller import ASPECT_ORDER, mode_text
from ui.pages.base import Page
from ui.widgets import ActionButton, ModeTile, Panel, SectionLabel, make_label, set_tone

ALL = "All"
MAX_COLUMNS = 6


class SwitchPage(Page):
    title = "Switch"
    subtitle = "Click a resolution to apply it. Right-click for refresh rates, saving and hiding."
    open_hotkeys = pyqtSignal()

    def __init__(self, controller, window, parent=None):
        super().__init__(controller, window, parent)
        self._tiles = []          # (preset, tile)
        self._group_labels = {}
        self._keys = None
        self._columns = 0

        # Display picker (only when there is a choice).
        self.display_row = QHBoxLayout()
        display_label = SectionLabel("Display")
        self.display_combo = QComboBox()
        self.display_combo.setAccessibleName("Display")
        display_label.setBuddy(self.display_combo)
        for d in controller.displays:
            name = d.get("string") or d.get("name")
            self.display_combo.addItem(f"{name}{'  ·  Primary' if d.get('primary') else ''}", d.get("name"))
        if controller.current_display:
            self.display_combo.setCurrentIndex(max(0, self.display_combo.findData(controller.dev_name())))
        self.display_combo.currentIndexChanged.connect(
            lambda i: controller.select_display(self.display_combo.itemData(i)))
        self.display_row.addWidget(display_label)
        self.display_row.addWidget(self.display_combo, 1)
        self.display_holder = QWidget()
        self.display_holder.setLayout(self.display_row)
        self.display_holder.setVisible(len(controller.displays) > 1)
        self.body_layout.addWidget(self.display_holder)

        # Quick toggle summary.
        quick = Panel("inset")
        quick_layout = QHBoxLayout(quick)
        quick_layout.setContentsMargins(t.SPACE_LG, t.SPACE_MD, t.SPACE_MD, t.SPACE_MD)
        quick_layout.setSpacing(t.SPACE_MD)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.quick_title = make_label("", role="strong")
        self.quick_detail = make_label("", role="caption", wrap=True)
        text_col.addWidget(self.quick_title)
        text_col.addWidget(self.quick_detail)
        quick_layout.addLayout(text_col, 1)
        self.quick_badge = make_label("", role="badge")
        quick_layout.addWidget(self.quick_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        edit = ActionButton("Edit")
        edit.setAccessibleName("Edit quick toggle")
        edit.clicked.connect(self.open_hotkeys.emit)
        toggle_now = ActionButton("Toggle Now", primary=True)
        toggle_now.clicked.connect(controller.toggle_stretch_native)
        quick_layout.addWidget(edit)
        quick_layout.addWidget(toggle_now)
        self.body_layout.addWidget(quick)

        # Filters.
        filter_row = QHBoxLayout()
        filter_row.setSpacing(t.SPACE_MD)
        self.segments = SegmentedControl([ALL], accessible_name="Aspect ratio filter")
        self.segments.changed.connect(lambda _v: self._apply_filter())
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search  (1440, 144, 4:3)")
        self.search.setAccessibleName("Search resolutions")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._apply_filter())
        filter_row.addWidget(self.segments)
        filter_row.addWidget(self.search, 1)
        self.count_label = make_label("", role="caption")
        filter_row.addWidget(self.count_label)
        self.body_layout.addLayout(filter_row)

        # Tile grid.
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(t.SPACE_SM)
        self.grid.setVerticalSpacing(t.SPACE_SM)
        self.empty_label = make_label("", role="muted", wrap=True, parent=self.grid_host)
        self.body_layout.addWidget(self.grid_host)
        self.finish()

        self.scroll.viewport().installEventFilter(self)
        controller.state_changed.connect(self.sync)
        controller.hotkey_changed.connect(self._sync_quick)
        controller.applying.connect(self._on_applying)
        controller.busy_changed.connect(self._on_busy)

    # -- quick toggle ---------------------------------------------------
    def _sync_quick(self):
        c = self.controller
        name, _vk, _mods = c.hotkey_config()
        self.quick_title.setText(f"Quick Toggle  ·  {name}")
        self.quick_detail.setText(f"Switches between native and {c.hotkey_target_text()}. Monitors are never changed.")
        if c.hotkey_registered:
            self.quick_badge.setText("Ready")
            set_tone(self.quick_badge, "accent")
        else:
            self.quick_badge.setText("Key unavailable")
            set_tone(self.quick_badge, "warning")

    # -- tiles ------------------------------------------------------------
    def sync(self):
        self._sync_quick()
        c = self.controller
        keys = [p.key for p in c.presets] + [tuple(c.rates_by_mode.get((p.w, p.h), [])) for p in c.presets]
        if keys != self._keys:
            self._keys = keys
            self._rebuild()
        else:
            info = c.current_mode()
            for preset, tile in self._tiles:
                tile.set_active(c.is_active(preset, info))
        groups = [ALL] + [g for g in ASPECT_ORDER if any(p.group == g for p in c.presets)]
        self.segments.set_options(groups)

    def _rebuild(self):
        for _p, tile in self._tiles:
            tile.hide()
            tile.deleteLater()
        for label in self._group_labels.values():
            label.hide()
            label.deleteLater()
        self._tiles, self._group_labels = [], {}
        c = self.controller
        info = c.current_mode()
        for preset in c.presets:
            tile = ModeTile(preset.w, preset.h, preset.group, preset.label, preset.is_custom, preset.hz,
                            is_active=c.is_active(preset, info),
                            rates=c.rates_by_mode.get((preset.w, preset.h), []), parent=self.grid_host)
            tile.apply_requested.connect(c.change_res)
            tile.save_requested.connect(c.save_mode)
            tile.delete_requested.connect(self._on_delete)
            tile.active_clicked.connect(lambda: c.notify.emit("That resolution is already active.", "", 3000))
            self._tiles.append((preset, tile))
            if preset.group not in self._group_labels:
                self._group_labels[preset.group] = SectionLabel(preset.group, self.grid_host)
        self._apply_filter()

    def _matches(self, preset, text, group):
        if group != ALL and preset.group != group:
            return False
        if not text:
            return True
        rates = self.controller.rates_by_mode.get((preset.w, preset.h), [])
        hay = " ".join([f"{preset.w}x{preset.h}", f"{preset.w}×{preset.h}", str(preset.w), str(preset.h),
                        preset.group, preset.label or "", *(str(r) for r in ([preset.hz] if preset.hz else rates))]).lower()
        return all(part in hay for part in text.lower().split())

    def _apply_filter(self):
        text = self.search.text().strip()
        group = self.segments.value() or ALL
        for preset, tile in self._tiles:
            tile.setVisible(self._matches(preset, text, group))
        if text or group != ALL:
            self.empty_label.setText("No resolutions match this filter.")
        else:
            self.empty_label.setText("No modes reported yet. EasyRes retries automatically after a display or driver change.")
        self._layout(force=True)

    def _column_count(self):
        width = self.scroll.viewport().width() - t.SPACE_2XL * 2
        return max(2, min(MAX_COLUMNS, (width + t.SPACE_SM) // (t.MODE_TILE_MIN_WIDTH + t.SPACE_SM)))

    def _layout(self, force=False):
        columns = self._column_count()
        if not force and columns == self._columns:
            return
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        row = 0
        for group in ASPECT_ORDER:
            tiles = [tile for preset, tile in self._tiles if preset.group == group and not tile.isHidden()]
            label = self._group_labels.get(group)
            if not tiles:
                if label:
                    label.hide()
                continue
            label.show()
            self.grid.addWidget(label, row, 0, 1, columns)
            row += 1
            for i, tile in enumerate(tiles):
                self.grid.addWidget(tile, row + i // columns, i % columns)
            row += (len(tiles) + columns - 1) // columns
        for col in range(MAX_COLUMNS):
            self.grid.setColumnStretch(col, 1 if col < columns else 0)
        visible = sum(1 for _p, tile in self._tiles if not tile.isHidden())
        self.empty_label.setVisible(visible == 0)
        self.grid.addWidget(self.empty_label, row, 0, 1, columns)
        total = len(self._tiles)
        self.count_label.setText(f"{visible} of {total}" if visible != total else f"{total} modes")

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport() and event.type() == event.Type.Resize:
            self._layout()
        return super().eventFilter(obj, event)

    # -- feedback -----------------------------------------------------------
    def _on_applying(self, w, h, hz):
        for _p, tile in self._tiles:
            if tile.res_width == w and tile.res_height == h and tile.hz == hz and not tile.isHidden():
                tile.set_pending(True)
                break
        else:
            for _p, tile in self._tiles:
                if tile.res_width == w and tile.res_height == h and not tile.is_custom:
                    tile.set_pending(True)
                    break
        self.grid_host.setEnabled(False)

    def _on_busy(self, busy):
        if not busy:
            for _p, tile in self._tiles:
                tile.set_pending(False)
            self.grid_host.setEnabled(True)

    def _on_delete(self, name, w, h, is_custom):
        if not is_custom:
            self.controller.hide_mode(w, h)
            return
        if self.window_.confirm(f"Remove “{name}”?",
                                "It's removed from My Modes. Any EDID override stays in place; "
                                "Custom → Restore Original EDID undoes that.",
                                "Remove", destructive=True):
            self.controller.remove_custom(name)

    def focus_search(self):
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()

    def matching_presets(self, text):
        return [p for p in self.controller.presets if self._matches(p, text, ALL)]

    def describe(self, preset):
        return mode_text(preset.w, preset.h, preset.hz)
