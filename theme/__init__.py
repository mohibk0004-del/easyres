"""EasyRes theme package."""

from theme.fonts import load_inter_font
from theme.motion import animations_enabled
from theme import tokens, styles

__all__ = ["load_inter_font", "animations_enabled", "tokens", "styles"]
