"""Font loading for EasyRes."""

import os

from PyQt6.QtGui import QFont, QFontDatabase

from theme import tokens as t
from theme.assets import asset_base_path

FONT_FILES = (
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
    "Inter-Bold.ttf",
)

# Tried in order when Inter is not bundled.
FALLBACK_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Inter")


def fonts_dir() -> str:
    return os.path.join(asset_base_path(), "assets", "fonts")


def load_app_font() -> QFont:
    """Load bundled Inter, falling back to the Windows UI font.

    Sizes are set in pixels so they match the px values used in QSS.
    """
    family = None
    for filename in FONT_FILES:
        path = os.path.join(fonts_dir(), filename)
        if os.path.isfile(path):
            font_id = QFontDatabase.addApplicationFont(path)
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    family = families[0]

    if not family:
        available = set(QFontDatabase.families())
        family = next((name for name in FALLBACK_FAMILIES if name in available), None)

    font = QFont(family) if family else QFont()
    font.setPixelSize(t.FONT_MD)
    font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    return font
