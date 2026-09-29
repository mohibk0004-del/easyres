"""Native Windows chrome for a frameless Qt window.

The window keeps Qt's FramelessWindowHint, but gets WS_THICKFRAME /
WS_CAPTION back so Windows provides: the DWM shadow, Win11 rounded corners,
Aero Snap, edge resizing and Snap Layouts on the maximize button. We hide
the native frame by answering WM_NCCALCSIZE and decide which pixels act as
caption / borders / maximize button in WM_NCHITTEST.

Everything fails soft: if any call fails, install() returns False and the
window keeps working with Qt-only move/resize.
"""

import ctypes
import os
from ctypes import wintypes

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_NCMOUSEMOVE = 0x00A0
WM_NCLBUTTONDOWN = 0x00A1
WM_NCLBUTTONUP = 0x00A2
WM_NCLBUTTONDBLCLK = 0x00A3
WM_NCMOUSELEAVE = 0x02A2
WM_MOUSEMOVE = 0x0200
WM_DISPLAYCHANGE = 0x007E
WM_SETTINGCHANGE = 0x001A

HTCLIENT = 1
HTCAPTION = 2
HTMAXBUTTON = 9
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 10, 11, 12, 13, 14, 15, 16, 17

GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_CAPTION = 0x00C00000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_SYSMENU = 0x00080000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x20

SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_ROUND = 2


class MARGINS(ctypes.Structure):
    _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


def is_supported():
    return os.name == "nt" and os.environ.get("EASYRES_QT_FRAME") != "1"


def _colorref(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return r | (g << 8) | (b << 16)


def _set_dwm_int(dwmapi, hwnd, attribute, value):
    data = ctypes.c_int(value)
    return dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), attribute, ctypes.byref(data), ctypes.sizeof(data))


def install(window, border_color="#1f1f1f"):
    """Enable native chrome for `window`. Returns True on success."""
    if not is_supported():
        return False
    try:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        hwnd = int(window.winId())
        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_style.restype = ctypes.c_ssize_t
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        set_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        style = get_style(hwnd, GWL_STYLE)
        style |= WS_THICKFRAME | WS_CAPTION | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_SYSMENU
        set_style(hwnd, GWL_STYLE, style)

        margins = MARGINS(1, 1, 1, 1)
        dwmapi.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins))
        _set_dwm_int(dwmapi, hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
        _set_dwm_int(dwmapi, hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)  # no-op on Windows 10
        _set_dwm_int(dwmapi, hwnd, DWMWA_BORDER_COLOR, _colorref(border_color))

        user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        return True
    except Exception:
        return False


def _frame_thickness(hwnd):
    user32 = ctypes.windll.user32
    try:
        dpi = user32.GetDpiForWindow(wintypes.HWND(hwnd))
        return (user32.GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi)
                + user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi))
    except Exception:
        return user32.GetSystemMetrics(SM_CXSIZEFRAME) + user32.GetSystemMetrics(SM_CXPADDEDBORDER)


def handle_msg(window, msg):
    """Process a Win32 MSG addressed to `window` (from an application-level
    native event filter; see ChromeEventFilter).

    `window` provides: native_chrome (bool), resize_border(),
    native_hit_test(QPoint) -> "client" | "caption" | "max",
    set_max_hover(bool), press_max(), on_display_change().
    Returns (handled, result).
    """
    kind = msg.message

    if kind == WM_NCCALCSIZE and window.native_chrome:
        if msg.wParam and window.isMaximized():
            # A maximized thick-frame window overhangs the monitor; inset so
            # content is not clipped.
            params = NCCALCSIZE_PARAMS.from_address(msg.lParam)
            inset = _frame_thickness(msg.hWnd)
            rect = params.rgrc[0]
            rect.left += inset
            rect.top += inset
            rect.right -= inset
            rect.bottom -= inset
        return True, 0

    if kind == WM_NCHITTEST and window.native_chrome:
        from PyQt6.QtGui import QCursor
        pos = window.mapFromGlobal(QCursor.pos())
        if not window.isMaximized():
            border = window.resize_border()
            x, y, w, h = pos.x(), pos.y(), window.width(), window.height()
            left, right, top, bottom = x < border, x >= w - border, y < border, y >= h - border
            if top and left:
                return True, HTTOPLEFT
            if top and right:
                return True, HTTOPRIGHT
            if bottom and left:
                return True, HTBOTTOMLEFT
            if bottom and right:
                return True, HTBOTTOMRIGHT
            if left:
                return True, HTLEFT
            if right:
                return True, HTRIGHT
            if top:
                return True, HTTOP
            if bottom:
                return True, HTBOTTOM
        area = window.native_hit_test(pos)
        if area == "max":
            window.set_max_hover(True)
            return True, HTMAXBUTTON
        window.set_max_hover(False)
        return True, (HTCAPTION if area == "caption" else HTCLIENT)

    if window.native_chrome:
        # Windows owns the maximize button's input (for Snap Layouts); mirror it.
        if kind in (WM_NCLBUTTONDOWN, WM_NCLBUTTONDBLCLK) and msg.wParam == HTMAXBUTTON:
            return True, 0
        if kind == WM_NCLBUTTONUP and msg.wParam == HTMAXBUTTON:
            window.press_max()
            return True, 0
        if kind == WM_NCMOUSEMOVE:
            window.set_max_hover(msg.wParam == HTMAXBUTTON)
        elif kind in (WM_NCMOUSELEAVE, WM_MOUSEMOVE):
            window.set_max_hover(False)

    if kind == WM_DISPLAYCHANGE:
        window.on_display_change()
    return False, 0
