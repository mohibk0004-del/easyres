import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui import MainWindow

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    with open("crash.log", "w") as f:
        pass
    sys.stderr = open("crash.log", "a")
    sys.stdout = sys.stderr

    if not is_admin():
        exe = sys.executable
        if exe.endswith("python.exe"):
            exe = exe.replace("python.exe", "pythonw.exe")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, " ".join(sys.argv), None, 1)
        sys.exit()

    try:
        from PyQt6.QtWidgets import QMessageBox
        app = QApplication(sys.argv)
        
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "icon.png")
        app.setWindowIcon(QIcon(icon_path))
        
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "EasyRes_SingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
            QMessageBox.critical(None, "EasyRes", "An instance of EasyRes is already running. Check your system tray.")
            sys.exit(0)
        
        # Enable High DPI scaling
        if hasattr(Qt := getattr(app, "setAttribute", None), "__call__"):
            pass
            
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
