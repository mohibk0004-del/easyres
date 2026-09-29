import sys
import os
import ctypes
import subprocess

from PyQt6.QtWidgets import QApplication

ERROR_ALREADY_EXISTS = 183
SINGLE_INSTANCE_MUTEX = "Local\\EasyRes_SingleInstance"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def log_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "EasyRes")
    os.makedirs(path, exist_ok=True)
    return path


def open_crash_log():
    """Redirect stdout/stderr to a per-user log (never the working dir,
    which is System32 for an elevated process)."""
    try:
        log = open(os.path.join(log_dir(), "crash.log"), "w", encoding="utf-8", buffering=1)
    except OSError:
        return None
    sys.stderr = log
    sys.stdout = log
    return log


def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            exe = exe[:-len("python.exe")] + "pythonw.exe"
        params = subprocess.list2cmdline([os.path.abspath(sys.argv[0])] + sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)


def main():
    if not is_admin():
        relaunch_as_admin()
        sys.exit(0)

    log = open_crash_log()
    try:
        from PyQt6.QtWidgets import QMessageBox
        from theme.fonts import load_app_font
        from theme.assets import asset_base_path
        from theme import styles
        from PyQt6.QtGui import QIcon

        app = QApplication(sys.argv)
        app.setStyle(styles.AppStyle())
        app.setStyleSheet(styles.app_qss())
        app.setWindowIcon(QIcon(os.path.join(asset_base_path(), "icon.png")))

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        mutex = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
        if not mutex or ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            QMessageBox.critical(None, "EasyRes", "EasyRes is already running. Check your system tray.")
            sys.exit(0)

        app.setFont(load_app_font())

        from ui.app_window import AppWindow
        window = AppWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if log:
            log.flush()


if __name__ == "__main__":
    main()
