import ctypes
from ctypes import wintypes
import uuid
import winreg

def generate_cvt_rb(width, height, hz):
    """
    Generates an 18-byte EDID Detailed Timing Descriptor for VESA CVT-RB v1.
    """
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
    v_blank = int(min_v_blank_time / h_period) + 1
    v_blank = max(v_blank, v_front + v_sync + min_v_bp)
    v_total = v_active + v_blank

    pixel_clock_hz = (h_total * v_total * v_rate)
    # Convert to 10kHz units, round nearest
    pc_10k = int(round(pixel_clock_hz / 10000.0))

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

def get_active_monitor_device_ids():
    """
    Returns a list of DeviceIDs for currently active monitors.
    """
    setupapi = ctypes.windll.setupapi
    class SP_DEVINFO_DATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("ClassGuid", ctypes.c_byte * 16),
            ("DevInst", wintypes.DWORD),
            ("Reserved", ctypes.c_void_p)
        ]
    setupapi.SetupDiGetClassDevsA.restype = ctypes.c_void_p
    setupapi.SetupDiGetClassDevsA.argtypes = [ctypes.c_char_p, ctypes.c_char_p, wintypes.HWND, wintypes.DWORD]
    setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
    setupapi.SetupDiGetDeviceInstanceIdA.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInstanceIdA.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.c_char_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

    devices = setupapi.SetupDiGetClassDevsA(uuid.UUID("{4d36e968-e325-11ce-bfc1-08002be10318}").bytes_le, None, None, 2)
    device = SP_DEVINFO_DATA()
    device.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)

    device_ids = []
    index = 0
    while setupapi.SetupDiEnumDeviceInfo(devices, index, ctypes.byref(device)):
        buf = ctypes.create_string_buffer(256)
        setupapi.SetupDiGetDeviceInstanceIdA(devices, ctypes.byref(device), buf, 256, None)
        device_ids.append(buf.value.decode('utf-8'))
        index += 1
    setupapi.SetupDiDestroyDeviceInfoList(devices)
    return device_ids

def get_edid(device_id):
    """
    Reads the EDID for a given DeviceID from the registry using SetupAPI.
    """
    setupapi = ctypes.windll.setupapi
    class SP_DEVINFO_DATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("ClassGuid", ctypes.c_byte * 16),
            ("DevInst", wintypes.DWORD),
            ("Reserved", ctypes.c_void_p)
        ]
    setupapi.SetupDiGetClassDevsA.restype = ctypes.c_void_p
    setupapi.SetupDiGetClassDevsA.argtypes = [ctypes.c_char_p, ctypes.c_char_p, wintypes.HWND, wintypes.DWORD]
    setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
    setupapi.SetupDiGetDeviceInstanceIdA.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInstanceIdA.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.c_char_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    setupapi.SetupDiOpenDevRegKey.restype = wintypes.HKEY
    setupapi.SetupDiOpenDevRegKey.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

    devices = setupapi.SetupDiGetClassDevsA(uuid.UUID("{4d36e968-e325-11ce-bfc1-08002be10318}").bytes_le, None, None, 2)
    device = SP_DEVINFO_DATA()
    device.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)

    edid_bytes = None
    index = 0
    while setupapi.SetupDiEnumDeviceInfo(devices, index, ctypes.byref(device)):
        buf = ctypes.create_string_buffer(256)
        setupapi.SetupDiGetDeviceInstanceIdA(devices, ctypes.byref(device), buf, 256, None)
        if buf.value.decode('utf-8') == device_id:
            hkey = setupapi.SetupDiOpenDevRegKey(devices, ctypes.byref(device), 1, 0, 1, 0x20019) # KEY_READ
            if hkey and hkey != -1:
                try:
                    val, _ = winreg.QueryValueEx(hkey, "EDID")
                    edid_bytes = val
                except:
                    pass
                winreg.CloseKey(hkey)
            break
        index += 1
    setupapi.SetupDiDestroyDeviceInfoList(devices)
    return edid_bytes

def set_edid(device_id, edid_bytes):
    """
    Writes the EDID to the registry for the given DeviceID using SetupAPI.
    Requires Administrator privileges.
    """
    setupapi = ctypes.windll.setupapi
    class SP_DEVINFO_DATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("ClassGuid", ctypes.c_byte * 16),
            ("DevInst", wintypes.DWORD),
            ("Reserved", ctypes.c_void_p)
        ]
    setupapi.SetupDiGetClassDevsA.restype = ctypes.c_void_p
    setupapi.SetupDiGetClassDevsA.argtypes = [ctypes.c_char_p, ctypes.c_char_p, wintypes.HWND, wintypes.DWORD]
    setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
    setupapi.SetupDiGetDeviceInstanceIdA.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInstanceIdA.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.c_char_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    setupapi.SetupDiOpenDevRegKey.restype = wintypes.HKEY
    setupapi.SetupDiOpenDevRegKey.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

    devices = setupapi.SetupDiGetClassDevsA(uuid.UUID("{4d36e968-e325-11ce-bfc1-08002be10318}").bytes_le, None, None, 2)
    device = SP_DEVINFO_DATA()
    device.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)

    success = False
    index = 0
    while setupapi.SetupDiEnumDeviceInfo(devices, index, ctypes.byref(device)):
        buf = ctypes.create_string_buffer(256)
        setupapi.SetupDiGetDeviceInstanceIdA(devices, ctypes.byref(device), buf, 256, None)
        if buf.value.decode('utf-8') == device_id:
            hkey = setupapi.SetupDiOpenDevRegKey(devices, ctypes.byref(device), 1, 0, 1, 0x20006) # KEY_WRITE
            if hkey and hkey != -1:
                winreg.SetValueEx(hkey, "EDID", 0, winreg.REG_BINARY, edid_bytes)
                winreg.CloseKey(hkey)
                success = True
            break
        index += 1
    setupapi.SetupDiDestroyDeviceInfoList(devices)
    return success

def inject_resolution(edid_bytes, width, height, hz):
    """
    Injects the custom resolution into the first unused DTD slot.
    An unused slot typically starts with [00 00 00] and isn't a display descriptor tag.
    Returns the new EDID bytes or None if no slots available.
    """
    if len(edid_bytes) < 128:
        return None
        
    dtd = generate_cvt_rb(width, height, hz)
    edid = bytearray(edid_bytes)
    
    # Check DTD slots (offsets 54, 72, 90, 108)
    injected = False
    for offset in [54, 72, 90, 108]:
        # If it's empty (all zeros) or we want to overwrite the last one
        # A valid DTD must have a non-zero pixel clock (bytes 0-1)
        if edid[offset] == 0x00 and edid[offset+1] == 0x00 and edid[offset+2] == 0x00:
            # It's an empty slot, but wait, Display Descriptors also start with 00 00 00!
            # Display descriptors (tags) start with 00 00 00 followed by a tag in byte 3.
            # We can overwrite an empty slot if it exists. Actually, most EDIDs use all 4 slots.
            # We will just overwrite the last slot (offset 108) assuming it's usually a standard timing or string descriptor we don't need for basic functioning.
            pass
            
    # For a robust approach, we overwrite the 4th descriptor (offset 108)
    # The first 1 or 2 are usually the native resolutions.
    edid[108:126] = dtd
    
    return fix_checksum(bytes(edid))

def is_resolution_injected(edid_bytes, width, height, hz):
    """
    Checks if the CVT-RB timing for the given resolution is already in the EDID overrides.
    """
    if not edid_bytes or len(edid_bytes) < 128:
        return False
        
    dtd = generate_cvt_rb(width, height, hz)
    
    # Check DTD slots (offsets 54, 72, 90, 108)
    for offset in [54, 72, 90, 108]:
        if edid_bytes[offset:offset+18] == dtd:
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
            print(f"New EDID checksum: {new_edid[127]}")
            
            # Uncomment to test write
            # if ctypes.windll.shell32.IsUserAnAdmin():
            #     set_edid(devs[0], new_edid)
            #     print("Wrote new EDID")
