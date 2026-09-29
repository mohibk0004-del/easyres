import ctypes
from ctypes import wintypes
import uuid

try:
    import winreg
except ImportError:  # Non-Windows (tests)
    winreg = None

MONITOR_CLASS_GUID = "{4d36e96e-e325-11ce-bfc1-08002be10318}"
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
DIGCF_PRESENT = 2
DICS_FLAG_GLOBAL = 1
DIREG_DEV = 1
KEY_READ = 0x20019
KEY_WRITE = 0x20006

DESCRIPTOR_OFFSETS = (54, 72, 90, 108)
# Display descriptor tags, in the order we are willing to replace them.
# 0x10 = dummy, 0xFF = serial string, 0xFE = unspecified text.
# 0xFC (monitor name) and 0xFD (range limits) are never replaced.
REPLACEABLE_TAGS = (0x10, 0xFF, 0xFE)
PROTECTED_TAGS = (0xFC, 0xFD)

MIN_DIMENSION = 320
MAX_DIMENSION = 4095  # 12-bit DTD active fields
MIN_REFRESH = 24
MAX_REFRESH = 500
MAX_PIXEL_CLOCK_10KHZ = 0xFFFF  # 16-bit DTD pixel clock field


class EdidError(ValueError):
    pass


def validate_mode(width, height, hz):
    """Raise EdidError if the mode cannot be encoded as a CVT-RB DTD."""
    if not all(isinstance(value, int) for value in (width, height, hz)):
        raise EdidError("Width, height and refresh rate must be whole numbers.")
    if not (MIN_DIMENSION <= width <= MAX_DIMENSION and MIN_DIMENSION <= height <= MAX_DIMENSION):
        raise EdidError(f"Width and height must be between {MIN_DIMENSION} and {MAX_DIMENSION}.")
    if not (MIN_REFRESH <= hz <= MAX_REFRESH):
        raise EdidError(f"Refresh rate must be between {MIN_REFRESH} and {MAX_REFRESH} Hz.")


def generate_cvt_rb(width, height, hz):
    """
    Generates an 18-byte EDID Detailed Timing Descriptor for VESA CVT-RB v1.
    """
    validate_mode(width, height, hz)
    h_active = width
    v_active = height
    v_rate = hz

    h_blank = 160
    h_total = h_active + h_blank
    h_sync_offset = 48
    h_sync_pulse = 32

    v_front = 3
    v_sync = 4
    min_v_bp = 6
    min_v_blank_time = 460.0 # microseconds

    h_period = ((1000000.0 / v_rate) - min_v_blank_time) / v_active
    if h_period <= 0:
        raise EdidError("Refresh rate is too high for this resolution.")
    v_blank = int(min_v_blank_time / h_period) + 1
    v_blank = max(v_blank, v_front + v_sync + min_v_bp)
    if v_blank > 0xFFF:
        raise EdidError("Vertical blanking does not fit in an EDID timing.")
    v_total = v_active + v_blank

    pixel_clock_hz = (h_total * v_total * v_rate)
    # Convert to 10kHz units, round nearest
    pc_10k = int(round(pixel_clock_hz / 10000.0))
    if pc_10k > MAX_PIXEL_CLOCK_10KHZ:
        raise EdidError("Pixel clock exceeds the EDID limit (655.35 MHz). Lower the resolution or refresh rate.")

    dtd = bytearray(18)
    dtd[0] = pc_10k & 0xFF
    dtd[1] = (pc_10k >> 8) & 0xFF
    dtd[2] = h_active & 0xFF
    dtd[3] = h_blank & 0xFF
    dtd[4] = ((h_active >> 8) << 4) | (h_blank >> 8)
    dtd[5] = v_active & 0xFF
    dtd[6] = v_blank & 0xFF
    dtd[7] = ((v_active >> 8) << 4) | (v_blank >> 8)
    dtd[8] = h_sync_offset & 0xFF
    dtd[9] = h_sync_pulse & 0xFF
    dtd[10] = ((v_front & 0xF) << 4) | (v_sync & 0xF)
    dtd[11] = (((h_sync_offset >> 8) & 0x3) << 6) | \
              (((h_sync_pulse >> 8) & 0x3) << 4) | \
              (((v_front >> 4) & 0x3) << 2) | \
              ((v_sync >> 4) & 0x3)
    dtd[12] = 0 # H size mm
    dtd[13] = 0 # V size mm
    dtd[14] = 0
    dtd[15] = 0
    dtd[16] = 0
    dtd[17] = 0x1E # +H -V digital separate
    return dtd

def fix_checksum(edid_bytes):
    """
    Recalculates the EDID checksum (byte 127).
    """
    edid = bytearray(edid_bytes)
    # The sum of all 128 bytes must equal 0 (modulo 256)
    edid[127] = 0
    checksum = sum(edid[:128]) % 256
    edid[127] = (256 - checksum) % 256
    return bytes(edid)


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", ctypes.c_byte * 16),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p)
    ]


def _setupapi():
    setupapi = ctypes.windll.setupapi
    setupapi.SetupDiGetClassDevsA.restype = ctypes.c_void_p
    setupapi.SetupDiGetClassDevsA.argtypes = [ctypes.c_char_p, ctypes.c_char_p, wintypes.HWND, wintypes.DWORD]
    setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
    setupapi.SetupDiGetDeviceInstanceIdA.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInstanceIdA.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.c_char_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    setupapi.SetupDiOpenDevRegKey.restype = ctypes.c_void_p
    setupapi.SetupDiOpenDevRegKey.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    return setupapi


def _iter_monitor_devices(setupapi, devices):
    """Yield (instance_id, SP_DEVINFO_DATA) for each monitor device."""
    index = 0
    while True:
        device = SP_DEVINFO_DATA()
        device.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        if not setupapi.SetupDiEnumDeviceInfo(devices, index, ctypes.byref(device)):
            return
        buf = ctypes.create_string_buffer(512)
        if setupapi.SetupDiGetDeviceInstanceIdA(devices, ctypes.byref(device), buf, len(buf), None):
            yield buf.value.decode("utf-8", errors="replace"), device
        index += 1


def _with_monitor_devices(callback):
    setupapi = _setupapi()
    devices = setupapi.SetupDiGetClassDevsA(uuid.UUID(MONITOR_CLASS_GUID).bytes_le, None, None, DIGCF_PRESENT)
    if not devices or devices == INVALID_HANDLE_VALUE:
        return None
    try:
        return callback(setupapi, devices)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devices)


def get_active_monitor_device_ids():
    """
    Returns a list of DeviceIDs for currently active monitors.
    """
    result = _with_monitor_devices(
        lambda setupapi, devices: [instance_id for instance_id, _ in _iter_monitor_devices(setupapi, devices)]
    )
    return result or []


def _open_device_key(setupapi, devices, device, access):
    hkey = setupapi.SetupDiOpenDevRegKey(devices, ctypes.byref(device), DICS_FLAG_GLOBAL, 0, DIREG_DEV, access)
    if not hkey or hkey == INVALID_HANDLE_VALUE:
        return None
    return hkey


def get_edid(device_id):
    """
    Reads the EDID for a given DeviceID from the registry using SetupAPI.
    """
    def read(setupapi, devices):
        for instance_id, device in _iter_monitor_devices(setupapi, devices):
            if instance_id != device_id:
                continue
            hkey = _open_device_key(setupapi, devices, device, KEY_READ)
            if hkey is None:
                return None
            try:
                value, _ = winreg.QueryValueEx(hkey, "EDID")
                return bytes(value)
            except OSError:
                return None
            finally:
                winreg.CloseKey(hkey)
        return None

    return _with_monitor_devices(read)

def set_edid(device_id, edid_bytes):
    """
    Writes the EDID to the registry for the given DeviceID using SetupAPI.
    Requires Administrator privileges.
    """
    if not edid_bytes or len(edid_bytes) < 128:
        return False

    def write(setupapi, devices):
        for instance_id, device in _iter_monitor_devices(setupapi, devices):
            if instance_id != device_id:
                continue
            hkey = _open_device_key(setupapi, devices, device, KEY_WRITE)
            if hkey is None:
                return False
            try:
                winreg.SetValueEx(hkey, "EDID", 0, winreg.REG_BINARY, bytes(edid_bytes))
                return True
            except OSError:
                return False
            finally:
                winreg.CloseKey(hkey)
        return False

    return bool(_with_monitor_devices(write))


def match_monitor_instance(display_device_id, active_ids):
    """
    Map an EnumDisplayDevices monitor ID (MONITOR\\<HWID>\\...) to a SetupAPI
    instance ID (DISPLAY\\<HWID>\\...). Returns None when the match is
    ambiguous so callers never write to the wrong monitor.
    """
    if not active_ids:
        return None
    hw_id = None
    if display_device_id and "\\" in display_device_id:
        parts = display_device_id.split("\\")
        if len(parts) > 1 and parts[1]:
            hw_id = parts[1].upper()
    if hw_id:
        matches = [aid for aid in active_ids if aid.upper().startswith(f"DISPLAY\\{hw_id}\\")]
        if len(matches) == 1:
            return matches[0]
        return None
    if len(active_ids) == 1:
        return active_ids[0]
    return None


def _descriptor_slot_for_injection(edid):
    """Pick a descriptor slot that is safe to overwrite, or None."""
    candidates = []
    for offset in DESCRIPTOR_OFFSETS[1:]:  # Slot 54 is the preferred native timing.
        block = edid[offset:offset + 18]
        is_display_descriptor = block[0] == 0 and block[1] == 0
        if not is_display_descriptor:
            continue  # A real detailed timing; never overwrite.
        tag = block[3]
        if tag in PROTECTED_TAGS:
            continue
        if all(byte == 0 for byte in block):
            rank = 0
        elif tag in REPLACEABLE_TAGS:
            rank = 1 + REPLACEABLE_TAGS.index(tag)
        else:
            rank = 10
        candidates.append((rank, offset))
    if not candidates:
        return None
    return min(candidates)[1]


def inject_resolution(edid_bytes, width, height, hz):
    """
    Injects the custom resolution into a descriptor slot that does not carry
    the native timing, monitor name, or range limits.
    Pass the monitor's original EDID so repeated injections replace the
    previous custom mode instead of consuming further slots.
    Returns the new EDID bytes or None if no safe slot is available.
    """
    if not edid_bytes or len(edid_bytes) < 128:
        return None

    dtd = generate_cvt_rb(width, height, hz)
    edid = bytearray(edid_bytes)
    offset = _descriptor_slot_for_injection(edid)
    if offset is None:
        return None
    edid[offset:offset + 18] = dtd
    return fix_checksum(bytes(edid))

def is_resolution_injected(edid_bytes, width, height, hz):
    """
    Checks if the CVT-RB timing for the given resolution is already in the EDID overrides.
    """
    if not edid_bytes or len(edid_bytes) < 128:
        return False
    try:
        dtd = generate_cvt_rb(width, height, hz)
    except EdidError:
        return False
    for offset in DESCRIPTOR_OFFSETS:
        if bytes(edid_bytes[offset:offset+18]) == bytes(dtd):
            return True
    return False

if __name__ == "__main__":
    devs = get_active_monitor_device_ids()
    if devs:
        print(f"Active display: {devs[0]}")
        edid = get_edid(devs[0])
        if edid:
            print(f"Read EDID ({len(edid)} bytes). Checksum: {edid[127]}")
            new_edid = inject_resolution(edid, 1440, 1080, 144)
            if new_edid:
                print(f"New EDID checksum: {new_edid[127]}")
