"""Application state and actions, independent of any widget.

Views call methods here and listen to signals. Every blocking system call
runs through ui.workers.run_async. Resolution actions never change monitor
power; only set_monitor_power() and reset_res(enable_monitors=True) do.
"""

import ctypes
import os
import threading

from PyQt6.QtCore import QObject, QSettings, QTimer, pyqtSignal

import driver
import edid
import resolution
import updater
from ui.workers import run_async

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
EDID_STEPS = ("Checking monitor", "Backing up EDID", "Writing override", "Restarting graphics driver", "Waiting for display")


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def aspect_bucket(width, height):
    if not width or not height:
        return "Other"
    ratio = width / height
    for label, target in (("16:9", 16 / 9), ("16:10", 16 / 10), ("4:3", 4 / 3), ("5:4", 5 / 4), ("21:9", 21 / 9)):
        if abs(ratio - target) < 0.03:
            return label
    return "Other"


def is_native(current, native):
    return bool(
        current and native and
        current["width"] == native["width"] and
        current["height"] == native["height"] and
        current.get("hz") == native.get("hz")
    )


def mode_text(w, h, hz=None):
    return f"{w} × {h}" + (f" @ {hz} Hz" if hz else "")


class Preset:
    __slots__ = ("w", "h", "group", "label", "is_custom", "hz")

    def __init__(self, w, h, group, label="", is_custom=False, hz=None):
        self.w, self.h, self.group, self.label, self.is_custom, self.hz = w, h, group, label, is_custom, hz

    @property
    def key(self):
        return (self.w, self.h, self.hz, self.is_custom, self.label)


class AppController(QObject):
    state_changed = pyqtSignal()          # display, status or mode list changed
    monitors_changed = pyqtSignal()
    busy_changed = pyqtSignal(bool)
    notify = pyqtSignal(str, str, int)    # text, tone ("", "success", "warning"), ms (0 = sticky)
    hotkey_changed = pyqtSignal()
    update_changed = pyqtSignal()
    revert_requested = pyqtSignal(str, object)   # mode text, previous mode dict
    revert_cancelled = pyqtSignal()
    edid_progress = pyqtSignal(int)       # index into EDID_STEPS, len() = done, -1 = failed
    applying = pyqtSignal(int, int, object)  # optimistic "switching to" hint for tiles
    _update_progress = pyqtSignal(int)    # emitted from the download thread, delivered queued

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings or QSettings("EasyRes", "App")
        self.displays = resolution.get_displays()
        self.current_display = next((d for d in self.displays if d.get("primary")), None) or (
            self.displays[0] if self.displays else None
        )
        self.presets = []
        self.rates_by_mode = {}
        self.hw_monitors = []
        self.hw_loaded = False
        self.monitor_pending = set()
        self.busy = False
        self.revert_pending = False
        self.hotkey_registered = False
        self.restore_hotkey_registered = False
        self.available_release = None
        self.update_status = ""        # "", "downloading", "restarting"
        self.update_percent = 0
        self._preset_cache = {}
        self._retry_pending = set()
        self.last_stretch_modes = self._load_last_stretch_modes()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self.refresh)
        self._update_progress.connect(self._on_update_progress)

    # ------------------------------------------------------------------
    # Settings (registry values are user-writable; validate everything)
    # ------------------------------------------------------------------
    def load_customs(self):
        raw = self.settings.value("custom_resolutions", [])
        if not isinstance(raw, list):
            return []
        customs = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            w, h = as_int(item.get("w")), as_int(item.get("h"))
            name = item.get("name")
            hz = as_int(item.get("hz")) if item.get("hz") is not None else None
            if not w or not h or w <= 0 or h <= 0 or not isinstance(name, str) or not name.strip():
                continue
            customs.append({"name": name.strip()[:64], "w": w, "h": h, "hz": hz})
        return customs

    def save_customs(self, customs):
        self.settings.setValue("custom_resolutions", customs)

    def load_hidden(self):
        raw = self.settings.value("hidden_presets", [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        return [item for item in raw if isinstance(item, str)] if isinstance(raw, list) else []

    def hotkey_target(self):
        raw = self.settings.value("hotkey_target_res", None)
        if not isinstance(raw, dict):
            return None
        w, h = as_int(raw.get("w")), as_int(raw.get("h"))
        hz = as_int(raw.get("hz")) if raw.get("hz") is not None else None
        if not w or not h or w <= 0 or h <= 0:
            return None
        return {"w": w, "h": h, "hz": hz}

    def set_hotkey_target(self, target):
        self.settings.setValue("hotkey_target_res", target)
        self.hotkey_changed.emit()

    def _load_last_stretch_modes(self):
        raw = self.settings.value("last_stretch_modes", {})
        return raw if isinstance(raw, dict) else {}

    def _remember_stretch(self, dev, w, h, hz):
        self.last_stretch_modes[dev] = {"w": w, "h": h, "hz": hz}
        self.settings.setValue("last_stretch_modes", self.last_stretch_modes)

    def edid_backups(self):
        raw = self.settings.value("edid_backups", {})
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}

    def has_edid_backup(self):
        return bool(self.edid_backups())

    def setting_bool(self, key, default=False):
        return self.settings.value(key, default, type=bool)

    def set_setting(self, key, value):
        self.settings.setValue(key, value)

    # ------------------------------------------------------------------
    # Display state
    # ------------------------------------------------------------------
    def dev_name(self):
        return self.current_display.get("name") if self.current_display else None

    def select_display(self, name):
        display = next((d for d in self.displays if d.get("name") == name), None)
        if display:
            self.current_display = display
            self.refresh()

    def current_mode(self):
        dev = self.dev_name()
        return resolution.get_current_resolution(dev) if dev else None

    def native_mode(self):
        dev = self.dev_name()
        return resolution.get_registry_resolution(dev) if dev else None

    def status(self):
        """Values for the status strip."""
        info, native = self.current_mode(), self.native_mode()
        result = {"resolution": "No display", "refresh": "--", "mode": "--", "monitors": "--",
                  "mode_tone": "", "resolution_tone": "warning", "monitors_tone": ""}
        if info:
            result["resolution"] = mode_text(info["width"], info["height"])
            result["resolution_tone"] = ""
            result["refresh"] = f"{info.get('hz') or '--'} Hz"
        if info and native:
            if is_native(info, native):
                result["mode"] = "Native"
            else:
                native_ratio = native["width"] / native["height"] if native["height"] else 0
                current_ratio = info["width"] / info["height"] if info["height"] else 0
                result["mode"] = "Stretched" if abs(native_ratio - current_ratio) > 0.02 else "Scaled"
                result["mode_tone"] = "accent"
        if not self.hw_loaded:
            result["monitors"] = "Checking…"
        elif not self.hw_monitors:
            result["monitors"] = "Not found"
        else:
            off = sum(1 for m in self.hw_monitors if not monitor_is_on(m))
            result["monitors"] = f"{off} off" if off else "All on"
            result["monitors_tone"] = "warning" if off else ""
        return result

    def schedule_refresh(self):
        """Debounced refresh, e.g. on WM_DISPLAYCHANGE."""
        self._refresh_timer.start()

    def refresh(self):
        dev = self.dev_name()
        modes = resolution.get_all_resolutions(dev) if dev else []
        rates, unique = {}, []
        for w, h, hz in modes:
            if hz > 0:
                rates.setdefault((w, h), set()).add(hz)
            if (w, h) not in unique:
                unique.append((w, h))
        if unique:
            self._preset_cache[dev] = (unique, rates)
            self._retry_pending.discard(dev)
        elif dev in self._preset_cache:
            unique, rates = self._preset_cache[dev]
            self._schedule_retry(dev)
        elif dev:
            self._schedule_retry(dev)
        self.rates_by_mode = {key: sorted(value, reverse=True) for key, value in rates.items()}

        hidden = set(self.load_hidden())
        presets = [Preset(c["w"], c["h"], "My Modes", c["name"], True, c["hz"]) for c in self.load_customs()]
        presets += [Preset(w, h, aspect_bucket(w, h)) for w, h in unique if f"{w}x{h}" not in hidden]
        self.presets = presets
        self.state_changed.emit()

    def _schedule_retry(self, dev):
        # Drivers briefly report no modes after an EDID/driver restart.
        if dev not in self._retry_pending:
            self._retry_pending.add(dev)
            QTimer.singleShot(750, lambda: self._retry(dev))

    def _retry(self, dev):
        self._retry_pending.discard(dev)
        if dev == self.dev_name():
            self.refresh()

    def is_active(self, preset, info=None):
        info = info if info is not None else self.current_mode()
        if not info:
            return False
        return preset.w == info["width"] and preset.h == info["height"] and (
            preset.hz is None or preset.hz == info.get("hz"))

    def _set_busy(self, busy):
        self.busy = busy
        self.busy_changed.emit(busy)

    def _say(self, text, tone="", ms=4000):
        self.notify.emit(text, tone, ms)

    # ------------------------------------------------------------------
    # Applying resolutions
    # ------------------------------------------------------------------
    def change_res(self, w, h, hz=None, confirm=True):
        if self.busy or self.revert_pending:
            self._say("Hold on, still applying the last change.")
            return
        dev = self.dev_name()
        if not dev:
            return
        previous = resolution.get_current_resolution(dev)
        text = mode_text(w, h, hz)
        self._set_busy(True)
        self.applying.emit(w, h, hz)
        self._say(f"Switching to {text}…", ms=0)

        def done(ok):
            self._set_busy(False)
            if not ok:
                self._say(f"Your display driver rejected {text}. Nothing changed.", "warning")
                self.refresh()
                return
            native = resolution.get_registry_resolution(dev)
            applied = resolution.get_current_resolution(dev) or {"width": w, "height": h, "hz": hz}
            if native and not is_native(applied, native):
                self._remember_stretch(dev, w, h, hz)
            self.refresh()
            self._say(f"Switched to {text}.", "success")
            changed = previous and (previous["width"], previous["height"]) != (w, h)
            if confirm and changed and self.setting_bool("ask_apply_res", True):
                self.revert_pending = True
                self.revert_requested.emit(text, previous)

        def failed(message):
            self._set_busy(False)
            self._say(f"Couldn't switch: {message}", "warning")
            self.refresh()

        run_async(resolution.set_resolution, w, h, hz, dev, on_done=done, on_error=failed)

    def keep_mode(self):
        self.revert_pending = False

    def revert_to(self, previous):
        self.revert_pending = False
        if previous:
            self.change_res(previous["width"], previous["height"], previous.get("hz"), confirm=False)
            self._say("Reverted to your previous resolution.")

    def toggle_stretch_native(self):
        if self.busy or self.revert_pending:
            return
        dev = self.dev_name()
        current, native = self.current_mode(), self.native_mode()
        if not dev or not current or not native:
            return
        if not is_native(current, native):
            self._remember_stretch(dev, current["width"], current["height"], current.get("hz"))
            self.reset_res(enable_monitors=False)
            return
        target = self.hotkey_target() or self.last_stretch_modes.get(dev)
        w = as_int(target.get("w")) if isinstance(target, dict) else None
        h = as_int(target.get("h")) if isinstance(target, dict) else None
        hz = as_int(target.get("hz")) if isinstance(target, dict) and target.get("hz") is not None else None
        if not w or not h or w <= 0 or h <= 0:
            self._say("Pick a stretch target on the Hotkeys page, or apply a stretched mode once.", "warning")
            return
        self.change_res(w, h, hz, confirm=False)

    def reset_res(self, enable_monitors=False):
        if self.revert_pending:
            # Restore Native wins over a pending keep/revert countdown.
            self.revert_pending = False
            self.revert_cancelled.emit()
        dev = self.dev_name()
        instance_ids = [m.get("Instance ID") for m in self.hw_monitors if m.get("Instance ID")] if enable_monitors else []
        self._say("Restoring native resolution…", ms=0)

        def work():
            failures = 0
            if enable_monitors:
                for instance_id in instance_ids:
                    if not resolution.set_hardware_monitor_state(instance_id, True):
                        failures += 1
                resolution.set_monitor_state(dev, True)
            return resolution.reset_resolution(dev), failures

        def done(result):
            ok, failures = result
            self.refresh()
            if enable_monitors:
                self.refresh_monitors()
            if not ok:
                self._say("Windows didn't accept the native mode. Try again or use Windows display settings.", "warning")
            elif failures:
                self._say(f"Native restored, but {failures} monitor(s) couldn't be enabled.", "warning")
            else:
                self._say("Native resolution restored" + (" and monitors enabled." if enable_monitors else "."), "success")

        run_async(work, on_done=done, on_error=lambda msg: self._say(f"Restore failed: {msg}", "warning"))

    # ------------------------------------------------------------------
    # Saved / hidden modes
    # ------------------------------------------------------------------
    def save_mode(self, w, h, hz):
        customs = self.load_customs()
        if any(c["w"] == w and c["h"] == h and c["hz"] == hz for c in customs):
            self._say(f"{mode_text(w, h, hz)} is already in My Modes.")
            return
        customs.append({"name": f"{w}×{h} @ {hz} Hz", "w": w, "h": h, "hz": hz})
        self.save_customs(customs)
        self.refresh()
        self._say(f"Saved {mode_text(w, h, hz)} to My Modes.", "success")

    def remove_custom(self, name):
        self.save_customs([c for c in self.load_customs() if c["name"] != name])
        self.refresh()
        self._say(f"Removed “{name}”.")

    def hide_mode(self, w, h):
        hidden = self.load_hidden()
        hidden.append(f"{w}x{h}")
        self.settings.setValue("hidden_presets", hidden)
        self.refresh()
        self._say(f"Hid {mode_text(w, h)}. Settings → Show Hidden Modes brings it back.")

    def show_hidden_modes(self):
        self.settings.setValue("hidden_presets", [])
        self.refresh()
        self._say("Hidden modes are visible again.")

    # ------------------------------------------------------------------
    # Custom resolution (EDID)
    # ------------------------------------------------------------------
    def refresh_rates_for(self, w, h):
        rates = resolution.get_monitor_refresh_rates(w, h, self.dev_name()) if w and h else []
        if rates:
            return rates, True
        current = self.current_mode()
        return ([current["hz"]] if current and current.get("hz") else []), False

    def validate_custom(self, w, h, hz, name, experimental):
        """Returns (error_text, [field names]) or (None, [])."""
        if not w or not h:
            return "Enter a width and height.", [f for f, v in (("w", w), ("h", h)) if not v]
        if hz is None:
            return "Choose a refresh rate.", ["hz"]
        try:
            edid.generate_cvt_rb(w, h, int(hz))
        except edid.EdidError as exc:
            return str(exc), ["w", "h"]
        if not experimental and (w, h) not in resolution.VALORANT_SAFE_RESOLUTIONS:
            return "Pick a listed mode, or turn on “Any size”.", []
        customs = self.load_customs()
        if name and any(c["name"] == name for c in customs):
            return "A saved mode already uses that name.", ["name"]
        if any(c["w"] == w and c["h"] == h and c["hz"] == hz for c in customs):
            return f"{mode_text(w, h, hz)} is already in My Modes.", []
        return None, []

    def add_custom(self, w, h, hz, name, on_done=None, on_error=None):
        """Write an EDID override and restart the driver. Caller confirms first."""
        if self.busy:
            return
        name = name or f"{w}×{h} @ {hz} Hz"
        dev_id = self.current_display.get("device_id") if self.current_display else None
        backups = self.edid_backups()
        progress = self.edid_progress
        self._set_busy(True)

        def work():
            progress.emit(0)
            target_id = edid.match_monitor_instance(dev_id, edid.get_active_monitor_device_ids())
            if not target_id:
                raise RuntimeError("Couldn't tell which monitor to modify, so nothing was changed.")
            current = edid.get_edid(target_id)
            if not current:
                raise RuntimeError("Couldn't read this monitor's EDID. Nothing was changed.")
            if edid.is_resolution_injected(current, w, h, int(hz)):
                return {"restarted": False, "driver_ok": True, "target": target_id, "backup": None}
            progress.emit(1)
            backup_hex = backups.get(target_id)
            original = bytes.fromhex(backup_hex) if backup_hex else bytes(current)
            new_edid = edid.inject_resolution(original, w, h, int(hz))
            if not new_edid:
                raise RuntimeError("This monitor's EDID has no free slot for a custom timing. Nothing was changed.")
            if not backup_hex:
                # Persist the backup before writing, from this thread's own QSettings.
                store = QSettings("EasyRes", "App")
                saved = store.value("edid_backups", {})
                saved = saved if isinstance(saved, dict) else {}
                saved[target_id] = original.hex()
                store.setValue("edid_backups", saved)
                store.sync()
            progress.emit(2)
            if not edid.set_edid(target_id, new_edid):
                raise RuntimeError("Windows refused the EDID write. Nothing was changed.")
            progress.emit(3)
            driver_ok = driver.restart_graphics_driver()
            return {"restarted": True, "driver_ok": driver_ok, "target": target_id}

        def done(result):
            customs = self.load_customs()
            customs.append({"name": name, "w": w, "h": h, "hz": hz})
            self.save_customs(customs)

            def finish():
                self._set_busy(False)
                progress.emit(len(EDID_STEPS))
                self.refresh()
                if result.get("restarted") and not result.get("driver_ok"):
                    self._say("Mode added, but the driver restart didn't finish. Reboot if the mode is missing.", "warning", 0)
                else:
                    self._say(f"Added {name}.", "success")
                if on_done:
                    on_done()

            if result.get("restarted"):
                progress.emit(4)
                QTimer.singleShot(4000, finish)
            else:
                finish()

        def failed(message):
            self._set_busy(False)
            progress.emit(-1)
            self._say("Custom resolution not added.", "warning")
            if on_error:
                on_error(message)

        run_async(work, on_done=done, on_error=failed)

    def restore_edid(self):
        backups = self.edid_backups()
        if not backups or self.busy:
            return
        self._set_busy(True)
        self._say("Restoring original EDID…", ms=0)

        def work():
            failures = [target for target, value in backups.items() if not edid.set_edid(target, bytes.fromhex(value))]
            return failures, driver.restart_graphics_driver()

        def done(result):
            failures, driver_ok = result
            if not failures:
                self.settings.remove("edid_backups")

            def finish():
                self._set_busy(False)
                self.refresh()
                if failures:
                    self._say("Some EDIDs couldn't be restored. Try again.", "warning")
                elif not driver_ok:
                    self._say("EDID restored. Reboot to finish.", "warning", 0)
                else:
                    self._say("Original EDID restored.", "success")

            QTimer.singleShot(4000, finish)

        def failed(message):
            self._set_busy(False)
            self._say(f"EDID restore failed: {message}", "warning")

        run_async(work, on_done=done, on_error=failed)

    # ------------------------------------------------------------------
    # Hardware monitors
    # ------------------------------------------------------------------
    def refresh_monitors(self):
        def done(monitors):
            self.hw_monitors = monitors or []
            self.hw_loaded = True
            self.monitors_changed.emit()
            self.state_changed.emit()

        run_async(resolution.get_hardware_monitors, on_done=done, on_error=lambda _m: done([]))

    def set_monitor_power(self, instance_id, enable, description):
        self.monitor_pending.add(instance_id)
        self.monitors_changed.emit()

        def done(ok):
            self.monitor_pending.discard(instance_id)
            if ok:
                self._say(f"{description} turned {'on' if enable else 'off'}.", "success")
            else:
                self._say(f"Windows couldn't turn {description} {'on' if enable else 'off'}.", "warning")
            self.refresh_monitors()
            self.refresh()

        run_async(resolution.set_hardware_monitor_state, instance_id, enable,
                  on_done=done, on_error=lambda _m: done(False))

    # ------------------------------------------------------------------
    # Hotkeys
    # ------------------------------------------------------------------
    def _user32(self):
        return ctypes.windll.user32

    def register_hotkeys(self):
        user32 = self._user32()
        user32.UnregisterHotKey(None, HOTKEY_ID_RESTORE)
        self.restore_hotkey_registered = bool(
            user32.RegisterHotKey(None, HOTKEY_ID_RESTORE, RESTORE_HOTKEY_MODS | MOD_NOREPEAT, RESTORE_HOTKEY_VK))
        self.apply_hotkey()

    def hotkey_config(self):
        vk = as_int(self.settings.value("toggle_hotkey_vk", DEFAULT_HOTKEY_VK))
        if vk is None or not (VK_F1 <= vk <= VK_F12):
            vk = DEFAULT_HOTKEY_VK
        mods = as_int(self.settings.value("toggle_hotkey_mods", 0)) or 0
        if mods not in {m for _label, m in HOTKEY_MODIFIERS}:
            mods = 0
        key = f"F{vk - VK_F1 + 1}"
        mod_label = next(label for label, m in HOTKEY_MODIFIERS if m == mods)
        return (key if not mods else f"{mod_label}+{key}"), vk, mods

    def apply_hotkey(self):
        user32 = self._user32()
        user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
        name, vk, mods = self.hotkey_config()
        self.settings.setValue("toggle_hotkey_name", name)
        self.hotkey_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_TOGGLE, mods | MOD_NOREPEAT, vk))
        self.hotkey_changed.emit()

    def set_hotkey(self, vk, mods):
        self.settings.setValue("toggle_hotkey_vk", vk)
        self.settings.setValue("toggle_hotkey_mods", mods)
        self.apply_hotkey()
        name, _vk, _mods = self.hotkey_config()
        if self.hotkey_registered:
            self._say(f"Quick toggle is now {name}.")
        else:
            self._say(f"{name} is taken by another app. Pick a different key.", "warning")

    def unregister_hotkeys(self):
        user32 = self._user32()
        user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
        user32.UnregisterHotKey(None, HOTKEY_ID_RESTORE)

    def hotkey_target_text(self):
        target = self.hotkey_target()
        if target:
            return mode_text(target["w"], target["h"], target["hz"])
        last = self.last_stretch_modes.get(self.dev_name())
        if isinstance(last, dict) and as_int(last.get("w")) and as_int(last.get("h")):
            return f"last stretched ({mode_text(as_int(last['w']), as_int(last['h']))})"
        return "last stretched mode"

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------
    def check_updates(self, silent=True, on_result=None):
        def done(release):
            latest = release.get("tag_name", "").lstrip("v")
            newer = bool(latest and updater.is_newer_version(latest, updater.CURRENT_VERSION))
            if newer:
                self.available_release = release
                self.update_changed.emit()
            if on_result:
                on_result(newer, latest, None)

        def failed(message):
            if on_result:
                on_result(False, None, message)

        run_async(updater.fetch_latest_release, on_done=done, on_error=failed)

    def available_version(self):
        return (self.available_release or {}).get("tag_name", "").lstrip("v")

    def start_update(self, on_ready):
        release = self.available_release
        if not release or self.update_status:
            return
        self.update_status = "downloading"
        self.update_percent = 0
        self.update_changed.emit()

        def download():
            asset = updater.select_windows_asset(release)
            return updater.download_asset(asset, self._update_progress.emit)

        def done(downloaded):
            self.update_status = "restarting"
            self.update_changed.emit()
            try:
                updater.launch_replacement(downloaded)
            except updater.UpdateError as exc:
                updater.discard_download(downloaded)
                failed(str(exc))
                return
            # The Qt event loop stops on quit, so the fallback exit needs a thread timer.
            force_exit = threading.Timer(3.0, lambda: os._exit(0))
            force_exit.daemon = True
            force_exit.start()
            on_ready()

        def failed(message):
            self.update_status = ""
            self.update_changed.emit()
            self._say(f"Update failed: {message} Your current version was not changed.", "warning", 0)

        run_async(download, on_done=done, on_error=failed)

    def _on_update_progress(self, percent):
        self.update_percent = percent
        self.update_changed.emit()


def monitor_is_on(monitor):
    return monitor.get("Status", "").lower() != "disabled"
