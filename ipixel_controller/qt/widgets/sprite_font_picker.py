"""Reusable sprite-font picker: 'Use sprite font' checkbox + font combo."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QWidget


class SpriteFontPicker(QWidget):
    """Checkbox + combo for choosing a sprite font.

    Emits ``changed()`` whenever the user toggles the checkbox or picks
    a different font. The combo is greyed out when the checkbox is off,
    but the previously-selected name is retained.
    """

    changed = Signal()

    def __init__(
        self,
        font_names: List[str],
        use_sprite: bool = False,
        font_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._check = QCheckBox("Use sprite font")
        self._check.setChecked(use_sprite)
        self._check.toggled.connect(self._on_toggle)
        layout.addWidget(self._check)

        layout.addWidget(QLabel("Font"))

        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        self._combo.currentIndexChanged.connect(lambda _i: self.changed.emit())
        layout.addWidget(self._combo, 1)

        self.set_fonts(font_names, font_name)
        self._refresh_enabled()

    # --------------------------------------------------------------- public
    def set_fonts(self, font_names: List[str], select: str = "") -> None:
        current = select or self._combo.currentText()
        self._combo.blockSignals(True)
        self._combo.clear()
        for name in font_names:
            self._combo.addItem(name)
        if current and current in font_names:
            self._combo.setCurrentText(current)
        elif font_names:
            self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)

    @property
    def use_sprite(self) -> bool:
        return self._check.isChecked()

    def set_use_sprite(self, value: bool) -> None:
        if value != self._check.isChecked():
            self._check.setChecked(value)

    @property
    def font_name(self) -> str:
        return self._combo.currentText()

    def set_font_name(self, name: str) -> None:
        if name:
            idx = self._combo.findText(name)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

    # -------------------------------------------------------------- internal
    def _on_toggle(self, _checked: bool) -> None:
        self._refresh_enabled()
        self.changed.emit()

    def _refresh_enabled(self) -> None:
        self._combo.setEnabled(self._check.isChecked())
