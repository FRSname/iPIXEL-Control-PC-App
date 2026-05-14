"""A button that displays its current colour and opens a colour picker."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QPushButton, QWidget


class ColorButton(QPushButton):
    """Square swatch button — click to pick a colour."""

    def __init__(
        self,
        color: str = "#FFFFFF",
        on_change: Optional[Callable[[str], None]] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._on_change = on_change
        self.setFixedSize(36, 28)
        self.setCursor(self.cursor())
        self.clicked.connect(self._open_picker)
        self._refresh_style()

    @property
    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self._refresh_style()
        if self._on_change:
            self._on_change(color)

    def _refresh_style(self) -> None:
        q = QColor(self._color)
        border = "#45475a" if q.lightness() > 60 else "#a6adc8"
        self.setStyleSheet(
            f"background-color: {self._color};"
            f"border: 1px solid {border};"
            "border-radius: 6px;"
        )

    def _open_picker(self) -> None:
        initial = QColor(self._color)
        chosen = QColorDialog.getColor(initial, self, "Pick colour")
        if chosen.isValid():
            self.set_color(chosen.name())
