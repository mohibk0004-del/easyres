"""QSS style builders for EasyRes."""

from theme import tokens as t


def container_qss(radius: int = t.RADIUS_XL, bordered: bool = True) -> str:
    border = f"border: 1px solid {t.BORDER_SUBTLE};" if bordered else "border: none;"
    return f"""
        QWidget#Container {{
            background-color: {t.BG_BASE};
            border-radius: {radius}px;
            {border}
        }}
    """


def dialog_container_qss() -> str:
    return f"""
        QWidget#Container {{
            background-color: {t.BG_BASE};
            border-radius: {t.RADIUS_XL}px;
            border: 1px solid {t.BORDER_SUBTLE};
        }}
    """


def title_bar_qss() -> str:
    return f"""
        background-color: {t.BG_ELEVATED};
        border-top-left-radius: {t.RADIUS_XL}px;
        border-top-right-radius: {t.RADIUS_XL}px;
        border-bottom: 1px solid {t.BORDER_SUBTLE};
    """


def section_card_qss(warning: bool = False) -> str:
    border_left = f"border-left: 3px solid {t.ACCENT_PRIMARY};" if warning else ""
    return f"""
        background-color: {t.BG_ELEVATED};
        border-radius: {t.RADIUS_LG}px;
        border: 1px solid {t.BORDER_SUBTLE};
        {border_left}
    """


def resolution_hero_qss() -> str:
    return f"""
        background-color: {t.BG_ELEVATED};
        border-radius: {t.RADIUS_XL}px;
        border: 1px solid {t.BORDER_SUBTLE};
    """


def section_label_qss() -> str:
    return f"""
        color: {t.TEXT_MUTED};
        font-size: {t.FONT_SM}px;
        font-weight: 600;
        letter-spacing: 1.5px;
        border: none;
        background: transparent;
    """


def body_label_qss() -> str:
    return f"""
        color: {t.TEXT_PRIMARY};
        font-size: {t.FONT_MD}px;
        font-weight: 500;
        border: none;
        background: transparent;
    """


def muted_label_qss(size: int = t.FONT_MD) -> str:
    return f"""
        color: {t.TEXT_MUTED};
        font-size: {size}px;
        border: none;
        background: transparent;
    """


def dialog_title_qss() -> str:
    return f"""
        color: {t.TEXT_PRIMARY};
        font-size: {t.FONT_XL}px;
        font-weight: 700;
        border: none;
        background: transparent;
    """


def title_label_qss() -> str:
    return f"""
        color: {t.TEXT_MUTED};
        font-weight: 600;
        font-size: {t.FONT_MD}px;
        border: none;
        background: transparent;
    """


def button_qss(primary: bool = False, destructive: bool = False) -> str:
    if destructive:
        bg = t.DESTRUCTIVE
        hover_bg = t.DESTRUCTIVE_HOVER
        border = t.DESTRUCTIVE
        pressed_bg = t.DESTRUCTIVE_HOVER
    elif primary:
        bg = t.ACCENT_PRIMARY
        hover_bg = t.ACCENT_HOVER
        border = t.ACCENT_PRIMARY
        pressed_bg = t.ACCENT_HOVER
    else:
        bg = t.BG_CARD_HOVER
        hover_bg = "#2a2a2b"
        border = t.BORDER_DEFAULT
        pressed_bg = t.ACCENT_PRIMARY

    return f"""
        QPushButton {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {t.RADIUS_LG}px;
            color: {t.TEXT_PRIMARY};
            font-size: {t.FONT_MD}px;
            font-weight: 600;
            padding: 10px;
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
            border: 1px solid {t.BORDER_HOVER if not primary and not destructive else border};
        }}
        QPushButton:pressed {{
            background-color: {pressed_bg};
            border: 1px solid {pressed_bg};
        }}
        QPushButton:focus {{
            border: 2px solid {t.ACCENT_PRIMARY};
        }}
    """


def icon_button_qss() -> str:
    return f"""
        QPushButton {{
            color: {t.TEXT_MUTED};
            background: transparent;
            border: none;
            border-radius: {t.RADIUS_SM}px;
            padding: 4px;
        }}
        QPushButton:hover {{
            color: {t.ACCENT_HOVER};
            background-color: {t.ACCENT_MUTED_BG};
        }}
        QPushButton:pressed {{
            color: {t.ACCENT_PRIMARY};
        }}
        QPushButton:focus {{
            border: 1px solid {t.ACCENT_PRIMARY};
        }}
    """


def update_badge_qss() -> str:
    return f"""
        QPushButton {{
            background-color: {t.DESTRUCTIVE};
            color: {t.TEXT_PRIMARY};
            border-radius: 10px;
            font-weight: 600;
            font-size: {t.FONT_SM}px;
            padding-left: 8px;
            padding-right: 8px;
            border: none;
        }}
        QPushButton:hover {{
            background-color: {t.DESTRUCTIVE_HOVER};
        }}
    """


def preset_card_qss(is_custom: bool = False, is_active: bool = False) -> str:
    base = t.BG_CARD_CUSTOM if is_custom else t.BG_CARD
    hover = t.BG_CARD_CUSTOM_HOVER if is_custom else t.BG_CARD_HOVER
    if is_active:
        border = f"2px solid {t.ACCENT_PRIMARY}"
        bg = t.BG_CARD_HOVER
    else:
        border = f"1px solid {t.BORDER_DEFAULT}"
        bg = base
    return f"""
        QPushButton {{
            background-color: {bg};
            border: {border};
            border-radius: {t.RADIUS_LG}px;
        }}
        QPushButton:hover {{
            background-color: {hover};
            border: 1px solid {t.BORDER_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {t.ACCENT_PRIMARY};
            border: 1px solid {t.ACCENT_PRIMARY};
        }}
        QPushButton:focus {{
            border: 2px solid {t.ACCENT_PRIMARY};
        }}
    """


def preset_card_label_qss(primary: bool = True) -> str:
    if primary:
        return f"color: {t.TEXT_PRIMARY}; font-size: {t.FONT_MD}px; font-weight: 600; border: none; background: transparent;"
    if primary is False:
        return f"color: {t.TEXT_MUTED}; font-size: {t.FONT_SM}px; font-weight: 500; border: none; background: transparent;"
    return f"color: rgba(134, 134, 139, 0.7); font-size: {t.FONT_XS}px; font-weight: 500; border: none; background: transparent;"


def input_qss(error: bool = False) -> str:
    border_color = t.DESTRUCTIVE if error else t.BORDER_DEFAULT
    focus_border = t.DESTRUCTIVE if error else t.ACCENT_PRIMARY
    return f"""
        QLineEdit {{
            background-color: {t.BG_CARD};
            border: 1px solid {border_color};
            border-radius: {t.RADIUS_MD}px;
            color: {t.TEXT_PRIMARY};
            padding: 6px;
            font-size: 12px;
        }}
        QLineEdit:focus {{
            border: 2px solid {focus_border};
        }}
    """


def combo_qss(elevated: bool = False) -> str:
    bg = t.BG_ELEVATED if elevated else t.BG_CARD
    border = t.BORDER_SUBTLE if elevated else t.BORDER_DEFAULT
    return f"""
        QComboBox {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {t.RADIUS_SM if elevated else t.RADIUS_MD}px;
            color: {t.TEXT_PRIMARY};
            padding: 4px 8px;
            font-size: 12px;
        }}
        QComboBox:focus {{
            border: 2px solid {t.ACCENT_PRIMARY};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {t.BG_CARD};
            color: {t.TEXT_PRIMARY};
            border: 1px solid {t.BORDER_DEFAULT};
            selection-background-color: {t.ACCENT_MUTED_BG};
            selection-color: {t.TEXT_PRIMARY};
        }}
    """


def scrollbar_qss() -> str:
    return f"""
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {t.BORDER_DEFAULT};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {t.ACCENT_PRIMARY};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
        }}
        QScrollBar::handle:horizontal {{
            background: {t.BORDER_DEFAULT};
            border-radius: 4px;
            min-width: 24px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {t.ACCENT_PRIMARY};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
    """


def menu_qss() -> str:
    return f"""
        QMenu {{
            background-color: {t.BG_CARD_HOVER};
            color: {t.TEXT_PRIMARY};
            border: 1px solid {t.BORDER_DEFAULT};
            border-radius: {t.RADIUS_SM}px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 20px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {t.ACCENT_MUTED_BG};
            color: {t.ACCENT_HOVER};
        }}
    """


def message_box_qss() -> str:
    return f"""
        QMessageBox {{
            background-color: {t.BG_BASE};
            color: {t.TEXT_PRIMARY};
        }}
        QMessageBox QLabel {{
            color: {t.TEXT_PRIMARY};
        }}
        QPushButton {{
            background-color: {t.BG_CARD_HOVER};
            color: {t.TEXT_PRIMARY};
            border: 1px solid {t.BORDER_DEFAULT};
            padding: 6px 16px;
            border-radius: {t.RADIUS_SM}px;
            min-width: 70px;
        }}
        QPushButton:hover {{
            background-color: #2a2a2b;
            border: 1px solid {t.ACCENT_PRIMARY};
        }}
        QPushButton:focus {{
            border: 2px solid {t.ACCENT_PRIMARY};
        }}
        QCheckBox {{
            color: {t.TEXT_PRIMARY};
        }}
    """


def experimental_badge_qss() -> str:
    return f"""
        color: {t.DESTRUCTIVE};
        font-size: {t.FONT_XS}px;
        font-weight: 600;
        background-color: {t.DESTRUCTIVE_MUTED_BG};
        border-radius: 4px;
        padding: 2px 6px;
    """
