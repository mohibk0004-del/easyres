"""Font loading for EasyRes."""

import os
import sys

from PyQt6.QtGui import QFont, QFontDatabase

FONT_FILES = {
    "Regular": "Inter-Regular.ttf",
    "Medium": "Inter-Medium.ttf",
    "SemiBold": "Inter-SemiBold.ttf",
    "Bold": "Inter-Bold.ttf",
}


def asset_base_path() -> str:
    try:
        return sys._MEIPASS
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fonts_dir() -> str:
    return os.path.join(asset_base_path(), "assets", "fonts")


def load_inter_font() -> QFont:
    """Load Inter from bundled assets; fall back to Segoe UI on Windows."""
    font_dir = fonts_dir()
    family = None
    for filename in FONT_FILES.values():
        path = os.path.join(font_dir, filename)
        if os.path.isfile(path):
            font_id = QFontDatabase.addApplicationFont(path)
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    family = families[0]

    if family:
        font = QFont(family, 13)
    else:
        font = QFont("Segoe UI", 13)
    font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    return font
