"""Motion utilities for EasyRes."""

import ctypes

SPI_GETCLIENTAREAANIMATION = 0x1042


def animations_enabled() -> bool:
    """Return False when Windows client area animations are disabled."""
    try:
        result = ctypes.c_int(0)
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(result), 0
        )
        return bool(result.value)
    except Exception:
        return True
