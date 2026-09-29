"""QSS for EasyRes.

One application-wide stylesheet, driven by widget properties, replaces
per-widget inline styles:

    label.setProperty("role", "muted")
    button.setProperty("variant", "primary")

Contrast rules (palette is fixed, so usage carries accessibility):
- White text sits on ACCENT_HOVER, never on ACCENT_PRIMARY (4.2:1).
- Blurple text only at >= 20px bold (large text, 3:1 minimum).
- Red text uses DESTRUCTIVE_HOVER (5:1); red fills are tints with a border.
"""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QProxyStyle, QStyle

from theme import tokens as t


class AppStyle(QProxyStyle):
    """Fusion base (consistent across Windows versions) with a thin chevron
    for combo-box arrows, which QSS cannot draw without image files."""

    def __init__(self):
        super().__init__("Fusion")

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            rect = option.rect
            cx, cy = rect.center().x() + 0.5, rect.center().y() + 0.5
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
            painter.setPen(QPen(QColor(t.TEXT_SECONDARY if enabled else t.TEXT_MUTED), 1.6,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline([QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2)])
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)


def repolish(widget):
    """Re-apply the stylesheet after a property change."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_props(widget, **props):
    for key, value in props.items():
        widget.setProperty(key, value)
    repolish(widget)


def _button(selector: str, bg: str, border: str, color: str, hover_bg: str, hover_border: str,
            pressed_bg: str, radius: int = t.RADIUS_MD, padding_v: int = 9, padding_h: int = 16) -> str:
    # Border width stays constant across states (focus changes colour only)
    # so content never shifts.
    return f"""
        {selector} {{
            background-color: {bg};
            border: 2px solid {border};
            border-radius: {radius}px;
            color: {color};
            font-size: {t.FONT_MD}px;
            font-weight: 600;
            padding: {padding_v}px {padding_h}px;
            min-height: 18px;
        }}
        {selector}:hover {{
            background-color: {hover_bg};
            border-color: {hover_border};
        }}
        {selector}:pressed {{
            background-color: {pressed_bg};
        }}
        {selector}:focus {{
            border-color: {t.ACCENT_PRIMARY};
        }}
        {selector}:disabled {{
            background-color: {t.BG_CARD};
            border-color: {t.BORDER_SUBTLE};
            color: {t.TEXT_MUTED};
        }}
    """


def app_qss() -> str:
    return f"""
        QWidget {{
            color: {t.TEXT_PRIMARY};
            font-size: {t.FONT_MD}px;
        }}
        QToolTip {{
            background-color: {t.BG_CARD_HOVER};
            color: {t.TEXT_PRIMARY};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_SM}px;
            padding: 6px 8px;
        }}

        /* ---------- Surfaces ---------- */
        QWidget#Root {{
            background-color: {t.BG_BASE};
        }}
        QWidget#Sidebar {{
            background-color: {t.BG_ELEVATED};
            border-right: 1px solid {t.BORDER_SUBTLE};
        }}
        QWidget#Header {{
            background-color: {t.BG_BASE};
            border-bottom: 1px solid {t.BORDER_SUBTLE};
        }}
        QWidget#ActionBar {{
            background-color: {t.BG_ELEVATED};
            border-top: 1px solid {t.BORDER_SUBTLE};
        }}
        QWidget#SheetCard, QWidget#DialogCard {{
            background-color: {t.BG_ELEVATED};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_XL}px;
        }}
        QFrame#Hairline {{
            background-color: {t.BORDER_SUBTLE};
            border: none;
            margin-left: {t.SPACE_LG}px;
        }}
        QListWidget#Palette {{
            background-color: {t.BG_CARD};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_MD}px;
            padding: 4px;
            outline: 0;
        }}
        QListWidget#Palette::item {{
            padding: 7px 10px;
            border-radius: {t.RADIUS_SM}px;
            color: {t.TEXT_PRIMARY};
        }}
        QListWidget#Palette::item:selected {{
            background-color: {t.ACCENT_MUTED_BG};
            color: {t.TEXT_PRIMARY};
        }}
        QWidget[panel="true"] {{
            background-color: {t.BG_ELEVATED};
            border: 1px solid {t.BORDER_SUBTLE};
            border-radius: {t.RADIUS_LG}px;
        }}
        QWidget[panel="inset"] {{
            background-color: {t.BG_CARD};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_MD}px;
        }}
        QWidget[panel="inset"][tone="warning"] {{
            border-color: {t.DESTRUCTIVE};
            background-color: {t.DESTRUCTIVE_MUTED_BG};
        }}
        QWidget[transparent="true"] {{
            background: transparent;
            border: none;
        }}

        /* ---------- Text ---------- */
        QLabel {{
            background: transparent;
            border: none;
        }}
        QLabel[role="app-title"] {{
            font-size: {t.FONT_LG}px;
            font-weight: 700;
        }}
        QLabel[role="page-title"] {{
            font-size: 22px;
            font-weight: 700;
        }}
        QLabel[role="dialog-title"] {{
            font-size: {t.FONT_XL}px;
            font-weight: 700;
        }}
        QLabel[role="section"] {{
            color: {t.TEXT_SECONDARY};
            font-size: {t.FONT_SM}px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        QLabel[role="body"] {{
            font-weight: 500;
        }}
        QLabel[role="strong"] {{
            font-weight: 600;
        }}
        QLabel[role="muted"] {{
            color: {t.TEXT_SECONDARY};
        }}
        QLabel[role="caption"] {{
            color: {t.TEXT_SECONDARY};
            font-size: {t.FONT_SM}px;
        }}
        QLabel[role="caption"][tone="warning"] {{
            color: {t.DESTRUCTIVE_HOVER};
        }}
        QLabel[role="value"] {{
            font-size: 20px;
            font-weight: 700;
        }}
        QLabel[role="value"][tone="accent"] {{
            color: {t.ACCENT_PRIMARY};
        }}
        QLabel[role="value"][tone="warning"] {{
            color: {t.DESTRUCTIVE_HOVER};
        }}
        QLabel[role="badge"] {{
            color: {t.TEXT_PRIMARY};
            font-size: {t.FONT_XS}px;
            font-weight: 700;
            background-color: {t.BG_CARD};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: 9px;
            padding: 3px 9px;
        }}
        QLabel[role="badge"][tone="accent"] {{
            background-color: {t.ACCENT_MUTED_BG};
            border-color: {t.ACCENT_MUTED_BORDER};
        }}
        QLabel[role="badge"][tone="warning"] {{
            background-color: {t.DESTRUCTIVE_MUTED_BG};
            border-color: {t.DESTRUCTIVE};
        }}

        /* ---------- Buttons ---------- */
        {_button('QPushButton', t.BG_CARD_HOVER, t.BORDER_DEFAULT, t.TEXT_PRIMARY,
                 t.BORDER_DEFAULT, t.BORDER_HOVER, t.BG_CARD)}
        {_button('QPushButton[variant="primary"]', t.ACCENT_HOVER, t.ACCENT_HOVER, t.TEXT_PRIMARY,
                 t.ACCENT_HOVER, t.ACCENT_PRIMARY, t.ACCENT_HOVER)}
        {_button('QPushButton[variant="destructive"]', t.DESTRUCTIVE_MUTED_BG, t.DESTRUCTIVE, t.TEXT_PRIMARY,
                 t.DESTRUCTIVE_MUTED_BG, t.DESTRUCTIVE_HOVER, t.BG_CARD)}
        QPushButton[variant="primary"]:focus {{
            border-color: {t.TEXT_PRIMARY};
        }}
        QPushButton[variant="pill"] {{
            background-color: {t.ACCENT_HOVER};
            border: 2px solid {t.ACCENT_HOVER};
            border-radius: 12px;
            color: {t.TEXT_PRIMARY};
            font-size: {t.FONT_SM}px;
            font-weight: 700;
            padding: 2px 12px;
            min-height: 16px;
            max-height: 16px;
        }}
        QPushButton[variant="pill"]:hover {{
            border-color: {t.ACCENT_PRIMARY};
        }}
        QPushButton[variant="pill"]:focus {{
            border-color: {t.TEXT_PRIMARY};
        }}
        QPushButton[variant="pill"]:disabled {{
            background-color: {t.BG_CARD_HOVER};
            border-color: {t.BORDER_DEFAULT};
            color: {t.TEXT_SECONDARY};
        }}
        QPushButton[variant="icon"] {{
            background: transparent;
            border: 2px solid transparent;
            border-radius: {t.RADIUS_SM}px;
            padding: 2px;
            min-height: 0px;
        }}
        QPushButton[variant="icon"]:hover, QPushButton[variant="icon"][hover="true"] {{
            background-color: {t.BG_CARD_HOVER};
        }}
        QPushButton[variant="icon"]:pressed {{
            background-color: {t.BORDER_DEFAULT};
        }}
        QPushButton[variant="icon"]:focus {{
            border-color: {t.ACCENT_PRIMARY};
        }}
        QPushButton[variant="icon"][danger="true"]:hover {{
            background-color: {t.DESTRUCTIVE};
        }}

        /* ---------- Inputs ---------- */
        QLineEdit, QComboBox {{
            background-color: {t.BG_CARD};
            border: 2px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_MD}px;
            color: {t.TEXT_PRIMARY};
            padding: 6px 10px;
            min-height: 18px;
            selection-background-color: {t.ACCENT_HOVER};
        }}
        QLineEdit:hover, QComboBox:hover {{
            border-color: {t.BORDER_HOVER};
        }}
        QLineEdit:focus, QComboBox:focus, QComboBox:on {{
            border-color: {t.ACCENT_PRIMARY};
        }}
        QLineEdit[error="true"] {{
            border-color: {t.DESTRUCTIVE};
        }}
        QLineEdit:disabled, QComboBox:disabled {{
            color: {t.TEXT_MUTED};
            background-color: {t.BG_ELEVATED};
            border-color: {t.BORDER_SUBTLE};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 22px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {t.BG_CARD};
            color: {t.TEXT_PRIMARY};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_SM}px;
            padding: 4px;
            outline: 0;
            selection-background-color: {t.ACCENT_MUTED_BG};
            selection-color: {t.TEXT_PRIMARY};
        }}
        QCheckBox {{
            color: {t.TEXT_PRIMARY};
            spacing: 8px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 2px solid {t.BORDER_HOVER};
            border-radius: 5px;
            background: {t.BG_CARD};
        }}
        QCheckBox::indicator:checked {{
            background: {t.ACCENT_HOVER};
            border-color: {t.ACCENT_PRIMARY};
        }}
        QCheckBox:focus {{
            color: {t.TEXT_PRIMARY};
        }}
        QCheckBox::indicator:focus {{
            border-color: {t.ACCENT_PRIMARY};
        }}

        /* ---------- Scrolling ---------- */
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {t.BORDER_DEFAULT};
            border-radius: 3px;
            min-height: 28px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {t.BORDER_HOVER};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            height: 0px;
            width: 0px;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            height: 0px;
        }}

        /* ---------- Menus ---------- */
        QMenu {{
            background-color: {t.BG_CARD_HOVER};
            color: {t.TEXT_PRIMARY};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_MD}px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 7px 20px;
            border-radius: {t.RADIUS_SM}px;
        }}
        QMenu::item:selected {{
            background-color: {t.ACCENT_MUTED_BG};
        }}
        QMenu::item:disabled {{
            color: {t.TEXT_MUTED};
        }}
        QMenu::separator {{
            height: 1px;
            background: {t.BORDER_DEFAULT};
            margin: 4px 6px;
        }}
    """
