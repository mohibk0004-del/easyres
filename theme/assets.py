"""Asset path helpers."""

import os
import sys


def asset_base_path() -> str:
    try:
        return sys._MEIPASS
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def icon_path(name: str) -> str:
    return os.path.join(asset_base_path(), "assets", "icons", name)
