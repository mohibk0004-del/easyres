import sys
import os
import ctypes
import faulthandler
import subprocess
import traceback

from PyQt6.QtWidgets import QApplication

ERROR_ALREADY_EXISTS = 183
SINGLE_INSTANCE_MUTEX = "Local\\EasyRes_SingleInstance"
SMOKE_ENV = "EASYRES_SMOKE_SECONDS"


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


def log_path():
    return os.path.join(log_dir(), "crash.log")


def open_crash_log():
    """Redirect stdout/stderr to a per-user log (never the working dir,
    which is System32 for an elevated process), and record native crashes."""
    try:
        log = open(log_path(), "w", encoding="utf-8", buffering=1)
    except OSError:
        return None
    sys.stderr = log
    sys.stdout = log
    faulthandler.enable(log)
    return log


def install_excepthook():
    """PyQt6 aborts the whole process on an unhandled exception inside a Qt
    callback unless a custom excepthook is set. Log it and keep running."""
    def hook(exc_type, exc, tb):
        traceback.print_exception(exc_type, exc, tb)
        if sys.stderr:
            sys.stderr.flush()
    sys.excepthook = hook


def show_startup_error():
    try:
        from PyQt6.QtWidgets import QMessageBox
        if QApplication.instance() is None:
            QApplication(sys.argv)
        QMessageBox.critical(None, "EasyRes couldn't start",
                             f"EasyRes hit an error while starting.\n\nDetails were saved to:\n{log_path()}")
    except Exception:
        pass


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


def arm_smoke_test(app, window):
    """CI: quit after N seconds and report whether the window came up."""
    seconds = os.environ.get(SMOKE_ENV)
    if not seconds:
        return
    from PyQt6.QtCore import QTimer

    def finish():
        print(f"SMOKE OK visible={window.isVisible()} native_chrome={window.native_chrome} "
              f"size={window.width()}x{window.height()}", flush=True)
        window._quit_app()

    QTimer.singleShot(int(float(seconds) * 1000), finish)


def main():
    if not is_admin():
        relaunch_as_admin()
        sys.exit(0)

    log = open_crash_log()
    install_excepthook()
    print(f"EasyRes starting (frozen={getattr(sys, 'frozen', False)}, python={sys.version.split()[0]})", flush=True)
    try:
        from PyQt6.QtWidgets import QMessageBox
        from theme.fonts import load_app_font
        from theme.assets import asset_base_path
        from theme import styles
        from PyQt6.QtGui import QIcon

        app = QApplication(sys.argv)
        styles.apply_app_style(app)
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
        print("Window shown", flush=True)
        arm_smoke_test(app, window)
        sys.exit(app.exec())
    except Exception:
        traceback.print_exc()
        show_startup_error()
        sys.exit(1)
    finally:
        if log:
            log.flush()


if __name__ == "__main__":
    main()
