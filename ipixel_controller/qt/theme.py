"""Dark theme palette + Qt Style Sheet for the iPixel Controller Qt UI.

Inspired by Catppuccin Mocha; tuned for an LED-panel control app. All
colours are exposed as constants so individual widgets can match the
sidebar/content split without hard-coding hexes everywhere.
"""

from __future__ import annotations

from PySide6.QtGui import QColor


# Background layers
BG_APP = "#1e1e2e"          # main content background
BG_SIDEBAR = "#181825"       # nav rail
BG_CARD = "#252537"          # card/panel surface
BG_INPUT = "#313244"         # text field, combobox

# Text
TEXT_PRIMARY = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
TEXT_MUTED = "#6c7086"

# Accent + state
ACCENT = "#89b4fa"           # primary action blue
ACCENT_HOVER = "#a4c4fb"
ACCENT_DOWN = "#6a9bf3"
SUCCESS = "#a6e3a1"
WARNING = "#f9e2af"
ERROR = "#f38ba8"
BORDER = "#45475a"

# Sidebar selection
NAV_ACTIVE_BG = "#313244"
NAV_HOVER_BG = "#262638"


def qcolor(hex_str: str) -> QColor:
    return QColor(hex_str)


STYLESHEET = f"""
* {{
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Helvetica", sans-serif;
    font-size: 10pt;
}}

QMainWindow, QWidget#ContentArea {{
    background-color: {BG_APP};
}}

QWidget#Sidebar {{
    background-color: {BG_SIDEBAR};
}}

QLabel#TitleLabel {{
    color: {TEXT_PRIMARY};
    font-size: 14pt;
    font-weight: 600;
    padding: 18px 18px 6px 18px;
}}

QLabel#SubtitleLabel {{
    color: {TEXT_MUTED};
    font-size: 9pt;
    padding: 0 18px 18px 18px;
}}

QLabel#PageHeader {{
    color: {TEXT_PRIMARY};
    font-size: 18pt;
    font-weight: 600;
}}

QLabel#PageSubheader {{
    color: {TEXT_SECONDARY};
    font-size: 10pt;
}}

QLabel#SectionLabel {{
    color: {TEXT_SECONDARY};
    font-size: 9pt;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QFrame#Card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* Nav buttons in the sidebar */
QPushButton#NavButton {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    text-align: left;
    padding: 10px 18px;
    border-left: 3px solid transparent;
    font-size: 10pt;
}}
QPushButton#NavButton:hover {{
    background-color: {NAV_HOVER_BG};
    color: {TEXT_PRIMARY};
}}
QPushButton#NavButton:checked {{
    background-color: {NAV_ACTIVE_BG};
    color: {TEXT_PRIMARY};
    border-left: 3px solid {ACCENT};
}}

/* Primary buttons */
QPushButton#PrimaryButton {{
    background-color: {ACCENT};
    color: #11111b;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton#PrimaryButton:pressed {{ background-color: {ACCENT_DOWN}; }}
QPushButton#PrimaryButton:disabled {{
    background-color: {BORDER};
    color: {TEXT_MUTED};
}}

/* Secondary buttons */
QPushButton {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background-color: {NAV_ACTIVE_BG}; }}
QPushButton:pressed {{ background-color: {NAV_HOVER_BG}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; }}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
    selection-color: #11111b;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: #11111b;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background: {BG_INPUT};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {TEXT_PRIMARY};
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

/* Checkbox */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    image: none;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; background: transparent;
}}

/* Connection bar */
QFrame#ConnectionBar {{
    background-color: {BG_CARD};
    border-bottom: 1px solid {BORDER};
}}
QLabel#StatusDot[state="connected"] {{ color: {SUCCESS}; }}
QLabel#StatusDot[state="disconnected"] {{ color: {ERROR}; }}
QLabel#StatusDot[state="connecting"] {{ color: {WARNING}; }}

/* Group labels */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    color: {TEXT_SECONDARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}

/* Tooltip */
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px 8px;
}}
"""
