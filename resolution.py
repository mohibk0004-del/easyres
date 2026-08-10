import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32

# Define constants
ENUM_CURRENT_SETTINGS = -1
ENUM_REGISTRY_SETTINGS = -2
CDS_TEST = 2
CDS_UPDATEREGISTRY = 1
CDS_NORESET = 268435456
DISP_CHANGE_SUCCESSFUL = 0

class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", ctypes.c_long),
        ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD)
    ]

class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128)
    ]

def get_displays():
    displays = []
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        # Only attached displays (or previously attached in registry)
        if dd.StateFlags & 1 or dd.StateFlags & 8: 
            displays.append({
                "name": dd.DeviceName,
                "string": dd.DeviceString,
                "device_id": dd.DeviceID,
                "primary": bool(dd.StateFlags & 4),
                "enabled": bool(dd.StateFlags & 1)
            })
        i += 1
    return displays

def get_current_resolution(device_name=None):
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    if user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return {
            "width": dm.dmPelsWidth,
            "height": dm.dmPelsHeight,
            "hz": dm.dmDisplayFrequency
        }
    return None

def set_resolution(width, height, device_name=None):
    best_dm = None
    best_hz = -1
    
    i = 0
    while True:
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(DEVMODEW)
        if not user32.EnumDisplaySettingsW(device_name, i, ctypes.byref(dm)):
            break
        
        if dm.dmPelsWidth == width and dm.dmPelsHeight == height:
            if dm.dmDisplayFrequency > best_hz:
                best_hz = dm.dmDisplayFrequency
                best_dm = dm
        i += 1
        
    if best_dm is not None:
        apply_dm = DEVMODEW()
        apply_dm.dmSize = ctypes.sizeof(DEVMODEW)
        if user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(apply_dm)):
            apply_dm.dmPelsWidth = best_dm.dmPelsWidth
            apply_dm.dmPelsHeight = best_dm.dmPelsHeight
            apply_dm.dmDisplayFrequency = best_dm.dmDisplayFrequency
            apply_dm.dmFields = 0x00080000 | 0x00100000 | 0x00400000 # DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY
            
            if user32.ChangeDisplaySettingsExW(device_name, ctypes.byref(apply_dm), None, CDS_TEST, None) == DISP_CHANGE_SUCCESSFUL:
                return user32.ChangeDisplaySettingsExW(device_name, ctypes.byref(apply_dm), None, 0, None) == DISP_CHANGE_SUCCESSFUL

    # Fallback for custom resolutions (tests before applying)
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    if user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        dm.dmPelsWidth = width
        dm.dmPelsHeight = height
        dm.dmFields = 0x00080000 | 0x00100000 # DM_PELSWIDTH | DM_PELSHEIGHT
        
        if user32.ChangeDisplaySettingsExW(device_name, ctypes.byref(dm), None, CDS_TEST, None) == DISP_CHANGE_SUCCESSFUL:
            return user32.ChangeDisplaySettingsExW(device_name, ctypes.byref(dm), None, 0, None) == DISP_CHANGE_SUCCESSFUL
            
    return False

import subprocess

def get_hardware_monitors():
    # Use pnputil to get hardware level monitor devices
    try:
        result = subprocess.run(["pnputil", "/enum-devices", "/class", "Monitor", "/connected"], 
                                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        monitors = []
        current_mon = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                if current_mon and "Instance ID" in current_mon:
                    monitors.append(current_mon)
                current_mon = {}
                continue
                
            if line.startswith("Instance ID:"):
                current_mon["Instance ID"] = line.split(":", 1)[1].strip()
            elif line.startswith("Device Description:"):
                current_mon["Device Description"] = line.split(":", 1)[1].strip()
            elif line.startswith("Status:"):
                current_mon["Status"] = line.split(":", 1)[1].strip()

        if current_mon and "Instance ID" in current_mon:
            monitors.append(current_mon)
            
        return monitors
    except Exception as e:
        return []

def set_hardware_monitor_state(instance_id, enable):
    # Requires Admin privileges
    try:
        cmd = ["pnputil", "/enable-device" if enable else "/disable-device", instance_id]
        subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception as e:
        return False

def reset_resolution(device_name=None):
    return user32.ChangeDisplaySettingsExW(device_name, None, None, 0, None) == DISP_CHANGE_SUCCESSFUL

def set_monitor_state(device_name, enabled):
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    if not enabled:
        # To disable, set dmPelsWidth = 0 and dmPelsHeight = 0
        if user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
            dm.dmPelsWidth = 0
            dm.dmPelsHeight = 0
            dm.dmFields = 0x00080000 | 0x00100000 # DM_PELSWIDTH | DM_PELSHEIGHT
            user32.ChangeDisplaySettingsExW(device_name, ctypes.byref(dm), None, CDS_UPDATEREGISTRY | CDS_NORESET, None)
            return user32.ChangeDisplaySettingsExW(None, None, None, 0, None) == DISP_CHANGE_SUCCESSFUL
    else:
        # To enable, fetch settings from registry
        if user32.EnumDisplaySettingsW(device_name, ENUM_REGISTRY_SETTINGS, ctypes.byref(dm)):
            user32.ChangeDisplaySettingsExW(device_name, ctypes.byref(dm), None, CDS_UPDATEREGISTRY | CDS_NORESET, None)
            return user32.ChangeDisplaySettingsExW(None, None, None, 0, None) == DISP_CHANGE_SUCCESSFUL
    return False
