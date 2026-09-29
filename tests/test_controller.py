"""AppController behaviour with Windows APIs stubbed out.

Key invariant: resolution actions (apply, hotkey toggle, Restore Native)
never change monitor power.
"""

import ctypes
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QCoreApplication, QSettings
except ImportError:  # pragma: no cover
    QCoreApplication = None

if not hasattr(ctypes, "windll"):
    ctypes.windll = mock.MagicMock()
    ctypes.windll.user32.RegisterHotKey.return_value = 1
sys.modules.setdefault("winreg", types.ModuleType("winreg"))

NATIVE = {"width": 1920, "height": 1080, "hz": 240}


@unittest.skipIf(QCoreApplication is None, "PyQt6 not installed")
class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.settings_dir = tempfile.TemporaryDirectory()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, cls.settings_dir.name)

    def setUp(self):
        import resolution
        self.current = dict(NATIVE)
        self.hw_calls = []
        self.monitor_state_calls = []
        patches = {
            "get_displays": lambda: [{"name": "D1", "string": "GPU", "device_id": r"MONITOR\ABC1234\x", "primary": True}],
            "get_all_resolutions": lambda dev=None: [(1920, 1080, 240), (1440, 1080, 240), (1280, 960, 144)],
            "get_current_resolution": lambda dev=None: dict(self.current),
            "get_registry_resolution": lambda dev=None: dict(NATIVE),
            "get_hardware_monitors": lambda: [{"Instance ID": "DISPLAY\\ABC1234\\1", "Device Description": "Panel",
                                               "Status": "Disabled"}],
            "set_hardware_monitor_state": lambda iid, en: self.hw_calls.append((iid, en)) or True,
            "set_monitor_state": lambda dev, en: self.monitor_state_calls.append(en) or True,
            "set_resolution": self._set_resolution,
            "reset_resolution": self._reset,
        }
        self._patchers = [mock.patch.object(resolution, name, value) for name, value in patches.items()]
        for patcher in self._patchers:
            patcher.start()
        from ui.controller import AppController
        settings = QSettings("EasyResTest", "Controller")
        settings.clear()
        self.controller = AppController(settings)
        self.controller.refresh()

    def tearDown(self):
        for patcher in self._patchers:
            patcher.stop()

    def _set_resolution(self, w, h, hz=None, dev=None):
        self.current = {"width": w, "height": h, "hz": hz or 240}
        return True

    def _reset(self, dev=None):
        self.current = dict(NATIVE)
        return True

    def wait_until(self, condition, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        self.fail("condition not met in time")

    def test_apply_requests_revert_and_revert_restores_previous(self):
        requested = []
        self.controller.revert_requested.connect(lambda text, previous: requested.append(previous))
        self.controller.change_res(1440, 1080, 240)
        self.wait_until(lambda: requested)
        self.assertEqual(self.current["width"], 1440)
        self.assertTrue(self.controller.revert_pending)
        self.controller.revert_to(requested[0])
        self.wait_until(lambda: self.current["width"] == 1920 and not self.controller.busy)

    def test_restore_native_cancels_pending_revert(self):
        cancelled = []
        self.controller.revert_cancelled.connect(lambda: cancelled.append(True))
        self.controller.change_res(1440, 1080, 240)
        self.wait_until(lambda: self.controller.revert_pending)
        self.controller.reset_res(enable_monitors=False)
        self.wait_until(lambda: self.current == NATIVE)
        self.assertTrue(cancelled)
        self.assertFalse(self.controller.revert_pending)

    def test_hotkey_toggles_between_native_and_target(self):
        self.controller.set_hotkey_target({"w": 1280, "h": 960, "hz": 144})
        self.controller.toggle_stretch_native()
        self.wait_until(lambda: self.current["width"] == 1280 and not self.controller.busy)
        self.assertFalse(self.controller.revert_pending)  # hotkeys never prompt
        self.controller.toggle_stretch_native()
        self.wait_until(lambda: self.current == NATIVE)

    def test_resolution_actions_never_touch_monitor_power(self):
        self.controller.refresh_monitors()
        self.wait_until(lambda: self.controller.hw_loaded)
        self.controller.set_hotkey_target({"w": 1280, "h": 960, "hz": 144})
        self.controller.change_res(1440, 1080, 240, confirm=False)
        self.wait_until(lambda: self.current["width"] == 1440 and not self.controller.busy)
        self.controller.toggle_stretch_native()
        self.wait_until(lambda: self.current == NATIVE)
        self.controller.toggle_stretch_native()
        self.wait_until(lambda: self.current["width"] == 1280 and not self.controller.busy)
        self.controller.reset_res(enable_monitors=False)
        self.wait_until(lambda: self.current == NATIVE)
        self.assertEqual(self.hw_calls, [])
        self.assertEqual(self.monitor_state_calls, [])

    def test_restore_with_monitors_enables_every_device(self):
        self.controller.refresh_monitors()
        self.wait_until(lambda: self.controller.hw_loaded)
        self.controller.reset_res(enable_monitors=True)
        self.wait_until(lambda: self.hw_calls)
        self.assertEqual(self.hw_calls, [("DISPLAY\\ABC1234\\1", True)])

    def test_custom_validation(self):
        c = self.controller
        self.assertIsNotNone(c.validate_custom(None, 1080, 144, "", False)[0])
        self.assertIsNotNone(c.validate_custom(1500, 1080, 144, "", False)[0])  # not a quick pick
        self.assertIsNone(c.validate_custom(1500, 1080, 144, "", True)[0])
        self.assertIsNotNone(c.validate_custom(5000, 1080, 144, "", True)[0])  # EDID bounds

    def test_malformed_settings_are_ignored(self):
        self.controller.settings.setValue("custom_resolutions", [{"w": "x"}, "junk", {"name": "ok", "w": 1440, "h": 1080}])
        self.assertEqual([c["name"] for c in self.controller.load_customs()], ["ok"])


if __name__ == "__main__":
    unittest.main()
