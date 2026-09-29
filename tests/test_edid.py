import unittest

import edid


def base_edid():
    data = bytearray(128)
    data[0:8] = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])
    # Slot 54: native detailed timing (non-zero pixel clock).
    data[54:72] = edid.generate_cvt_rb(1920, 1080, 60)
    # Slot 72: range limits descriptor.
    data[72:77] = bytes([0, 0, 0, 0xFD, 0])
    # Slot 90: monitor name descriptor.
    data[90:95] = bytes([0, 0, 0, 0xFC, 0])
    # Slot 108: serial string descriptor.
    data[108:113] = bytes([0, 0, 0, 0xFF, 0])
    return edid.fix_checksum(bytes(data))


class EdidTests(unittest.TestCase):
    def test_checksum_sums_to_zero(self):
        self.assertEqual(sum(base_edid()[:128]) % 256, 0)

    def test_injection_skips_native_name_and_range_limits(self):
        original = base_edid()
        injected = edid.inject_resolution(original, 1440, 1080, 144)
        self.assertEqual(injected[54:108], original[54:108])
        self.assertEqual(injected[108:126], bytes(edid.generate_cvt_rb(1440, 1080, 144)))
        self.assertEqual(sum(injected[:128]) % 256, 0)
        self.assertTrue(edid.is_resolution_injected(injected, 1440, 1080, 144))

    def test_injection_refuses_when_no_safe_slot(self):
        data = bytearray(base_edid())
        data[108:126] = edid.generate_cvt_rb(1280, 1024, 60)  # real timing
        self.assertIsNone(edid.inject_resolution(bytes(data), 1440, 1080, 144))

    def test_bounds_are_enforced(self):
        for mode in ((5000, 1080, 60), (1440, 100, 60), (1440, 1080, 1000), (4095, 4095, 240)):
            with self.assertRaises(edid.EdidError):
                edid.generate_cvt_rb(*mode)

    def test_monitor_matching_never_guesses(self):
        active = [r"DISPLAY\AUS2723\5&1", r"DISPLAY\BOE0900\5&2"]
        self.assertEqual(edid.match_monitor_instance(r"MONITOR\BOE0900\{guid}\0001", active), active[1])
        self.assertIsNone(edid.match_monitor_instance(r"MONITOR\XYZ0000\{guid}\0001", active))
        self.assertIsNone(edid.match_monitor_instance(None, active))
        self.assertEqual(edid.match_monitor_instance(None, active[:1]), active[0])


if __name__ == "__main__":
    unittest.main()
