import ctypes
from ctypes import wintypes
import uuid
import time

def restart_graphics_driver():
    """
    Restarts the graphics driver by disabling and re-enabling it via SetupAPI.
    Requires Administrator privileges.
    Returns True only if every adapter that was disabled is enabled again.
    """
    setupapi = ctypes.windll.setupapi

    class SP_DEVINFO_DATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("ClassGuid", ctypes.c_byte * 16),
            ("DevInst", wintypes.DWORD),
            ("Reserved", ctypes.c_void_p)
        ]

    class SP_CLASSINSTALL_HEADER(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("InstallFunction", wintypes.DWORD)
        ]

    class SP_PROPCHANGE_PARAMS(ctypes.Structure):
        _fields_ = [
            ("ClassInstallHeader", SP_CLASSINSTALL_HEADER),
            ("StateChange", wintypes.DWORD),
            ("Scope", wintypes.DWORD),
            ("HwProfile", wintypes.DWORD)
        ]

    setupapi.SetupDiGetClassDevsA.restype = ctypes.c_void_p
    setupapi.SetupDiGetClassDevsA.argtypes = [ctypes.c_char_p, ctypes.c_char_p, wintypes.HWND, wintypes.DWORD]

    setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]

    setupapi.SetupDiSetClassInstallParamsA.restype = wintypes.BOOL
    setupapi.SetupDiSetClassInstallParamsA.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.POINTER(SP_PROPCHANGE_PARAMS), wintypes.DWORD]

    setupapi.SetupDiCallClassInstaller.restype = wintypes.BOOL
    setupapi.SetupDiCallClassInstaller.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA)]

    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

    DIGCF_PRESENT = 2
    DIF_PROPERTYCHANGE = 0x12
    DICS_ENABLE = 1
    DICS_DISABLE = 2
    DICS_FLAG_GLOBAL = 1

    display_guid = uuid.UUID("{4d36e968-e325-11ce-bfc1-08002be10318}")
    guid_bytes = display_guid.bytes_le

    devices = setupapi.SetupDiGetClassDevsA(guid_bytes, None, None, DIGCF_PRESENT)
    if not devices or devices == ctypes.c_void_p(-1).value:
        return False

    def change_state(index, state):
        device = SP_DEVINFO_DATA()
        device.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        if not setupapi.SetupDiEnumDeviceInfo(devices, index, ctypes.byref(device)):
            return None
        params = SP_PROPCHANGE_PARAMS()
        params.ClassInstallHeader.cbSize = ctypes.sizeof(SP_CLASSINSTALL_HEADER)
        params.ClassInstallHeader.InstallFunction = DIF_PROPERTYCHANGE
        params.StateChange = state
        params.Scope = DICS_FLAG_GLOBAL
        params.HwProfile = 0
        if not setupapi.SetupDiSetClassInstallParamsA(devices, ctypes.byref(device), ctypes.byref(params), ctypes.sizeof(SP_PROPCHANGE_PARAMS)):
            return False
        return bool(setupapi.SetupDiCallClassInstaller(DIF_PROPERTYCHANGE, devices, ctypes.byref(device)))

    try:
        # Only touch adapters we successfully disabled, so we never enable
        # a device the user had disabled on purpose.
        disabled = []
        index = 0
        while True:
            result = change_state(index, DICS_DISABLE)
            if result is None:
                break
            if result:
                disabled.append(index)
            index += 1

        if not disabled:
            return False

        # Wait for the system to process the disable
        time.sleep(1.0)

        # Re-enable every adapter we disabled; retry so a transient failure
        # never leaves the machine on the basic display driver.
        pending = list(disabled)
        for _attempt in range(5):
            pending = [idx for idx in pending if not change_state(idx, DICS_ENABLE)]
            if not pending:
                break
            time.sleep(0.5)
        return not pending
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devices)

if __name__ == "__main__":
    if ctypes.windll.shell32.IsUserAnAdmin():
        print("Restarting graphics drivers...")
        success = restart_graphics_driver()
        print(f"Success: {success}")
    else:
        print("Admin privileges required.")
