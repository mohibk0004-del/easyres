import sys
from PyQt6.QtWidgets import QApplication
from ui import MainWindow

def main():
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "EasyRes_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        sys.exit(0)

    app = QApplication(sys.argv)
    
    # Enable High DPI scaling
    if hasattr(Qt := getattr(app, "setAttribute", None), "__call__"):
        # PyQt6 handles high dpi automatically, but just in case
        pass
        
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
