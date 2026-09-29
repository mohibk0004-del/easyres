"""Motion utilities for EasyRes."""

import ctypes
from functools import lru_cache

SPI_GETCLIENTAREAANIMATION = 0x1042


@lru_cache(maxsize=1)
def animations_enabled() -> bool:
    """Return False when Windows client area animations are disabled
    (Settings > Accessibility > Visual effects > Animation effects)."""
    try:
        result = ctypes.c_int(0)
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(result), 0
        )
        return bool(result.value)
    except Exception:
        return True


def duration(ms: int) -> int:
    """Animation duration honoring the Windows reduced-motion setting."""
    return ms if animations_enabled() else 0
