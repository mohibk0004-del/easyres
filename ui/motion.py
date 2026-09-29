"""Animation helpers. Every helper honors the Windows reduced-motion setting
(theme.motion.duration returns 0), in which case values jump to the end.

No bounce or elastic curves: motion only confirms state changes.
"""

import math

from PyQt6.QtCore import QEasingCurve, QVariantAnimation

from theme import tokens as t
from theme.motion import duration


def _critically_damped(progress: float) -> float:
    """Spring with damping ratio 1.0 (no overshoot), normalized to [0, 1]."""
    if progress >= 1.0:
        return 1.0
    omega = t.SPRING_OMEGA
    return 1.0 - (1.0 + omega * progress) * math.exp(-omega * progress)


def spring_curve() -> QEasingCurve:
    curve = QEasingCurve()
    curve.setCustomType(_critically_damped)
    return curve


def ease_out() -> QEasingCurve:
    return QEasingCurve(QEasingCurve.Type.OutCubic)


def ease_in() -> QEasingCurve:
    return QEasingCurve(QEasingCurve.Type.InCubic)


def stop(anim):
    """Stop an animation returned by tween()/spring(), if still running."""
    if anim is not None:
        try:
            anim.stop()
        except RuntimeError:  # already deleted
            pass


def tween(owner, start, end, ms, on_value, on_finished=None, curve=None):
    """Animate a value from start to end, calling on_value(v) each frame.

    Returns the running QVariantAnimation (parented to `owner`, deleted when
    stopped), or None when motion is off (on_value(end) applied at once).
    Callers keep the handle and pass it to stop() before starting another.
    """
    ms = duration(ms)
    if ms <= 0:
        on_value(end)
        if on_finished:
            on_finished()
        return None

    anim = QVariantAnimation(owner)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setDuration(ms)
    anim.setEasingCurve(curve or ease_out())
    anim.valueChanged.connect(on_value)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def spring(owner, start, end, on_value, on_finished=None, ms=None):
    return tween(owner, start, end, ms or t.MOTION_SPRING, on_value, on_finished, spring_curve())
