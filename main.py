import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui import MainWindow

def main():
    import ctypes
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
        # PyQt6 handles high dpi automatically, but just in case
        pass
        
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
