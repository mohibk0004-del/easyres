"""EasyRes theme package."""

from theme.fonts import load_app_font
from theme.motion import animations_enabled, duration
from theme import tokens, styles

__all__ = ["load_app_font", "animations_enabled", "duration", "tokens", "styles"]
