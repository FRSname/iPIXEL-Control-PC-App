"""Left navigation rail with selectable feature buttons."""

from __future__ import annotations

from typing import Callable, List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QWidget):
    """Vertical nav with a title, subtitle and a list of nav buttons.

    Emits ``selected(key)`` when the user picks a destination.
    """

    selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        title = QLabel("iPixel")
        title.setObjectName("TitleLabel")
        self._layout.addWidget(title)

        subtitle = QLabel("LED Panel Controller")
        subtitle.setObjectName("SubtitleLabel")
        self._layout.addWidget(subtitle)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

    def add_item(self, key: str, label: str, icon: str = "") -> QPushButton:
        text = f"  {icon}   {label}" if icon else label
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
        self._group.addButton(btn)
        self._layout.addWidget(btn)
        self._buttons[key] = btn
        return btn

    def add_section(self, name: str) -> None:
        label = QLabel(name.upper())
        label.setObjectName("SectionLabel")
        label.setContentsMargins(18, 14, 18, 4)
        self._layout.addWidget(label)

    def add_stretch(self) -> None:
        self._layout.addStretch()

    def select(self, key: str) -> None:
        btn = self._buttons.get(key)
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)
