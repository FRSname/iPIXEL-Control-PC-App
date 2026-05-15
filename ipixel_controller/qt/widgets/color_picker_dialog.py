"""Small themed colour picker dialog.

Self-contained so we never have to show Qt's ``QColorDialog`` (which
inherits our app stylesheet and renders badly). Provides:

- A live preview swatch + ``#rrggbb`` hex input
- A 6×6 grid of LED-panel-friendly preset colours
- Hue / Saturation / Value sliders for arbitrary HSV picking
- All three (hex / presets / HSV) stay in sync

API:
    color = pick_color(initial='#ff0000', parent=self)
    if color is not None:
        # accepted; ``color`` is a '#rrggbb' string
"""

from __future__ import annotations

import re
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


# 6×6 palette tuned for LED-panel use (high-saturation, primary, common neutrals).
PRESETS: List[str] = [
    "#000000", "#202020", "#404040", "#808080", "#c0c0c0", "#ffffff",
    "#ff0000", "#ff4000", "#ff8000", "#ffc000", "#ffff00", "#c0ff00",
    "#80ff00", "#40ff00", "#00ff00", "#00ff80", "#00ffff", "#0080ff",
    "#0040ff", "#0000ff", "#4000ff", "#8000ff", "#c000ff", "#ff00ff",
    "#ff0080", "#a00000", "#006000", "#000060", "#604000", "#202060",
    "#ff8080", "#80ff80", "#8080ff", "#ffff80", "#80ffff", "#ff80ff",
]


_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _is_valid_hex(s: str) -> bool:
    return _HEX_RE.match(s.strip()) is not None


def _normalise(s: str) -> str:
    m = _HEX_RE.match(s.strip())
    return f"#{m.group(1).lower()}" if m else "#000000"


class _Swatch(QPushButton):
    """A fixed-size square button that just shows a colour."""

    def __init__(self, color: str, on_click) -> None:
        super().__init__()
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"background-color: {color};"
            "border: 1px solid #45475a;"
            "border-radius: 4px;"
        )
        self._color = color
        self.clicked.connect(lambda: on_click(color))


class ColorPickerDialog(QDialog):
    """Themed colour picker. Returns a ``#rrggbb`` hex string."""

    def __init__(self, initial: str = "#FFFFFF", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pick colour")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._color = _normalise(initial)
        # Re-entrancy guard: any of the three input paths (hex / sliders /
        # preset) updates the others without re-triggering callbacks.
        self._suspend_sync = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        # ---- Preview + hex input row ----
        top = QHBoxLayout()
        top.setSpacing(10)
        self._preview = QFrame()
        self._preview.setFixedSize(56, 36)
        top.addWidget(self._preview)

        top.addWidget(QLabel("Hex"))
        self._hex_edit = QLineEdit(self._color)
        self._hex_edit.setMaxLength(7)
        self._hex_edit.setPlaceholderText("#rrggbb")
        self._hex_edit.textEdited.connect(self._on_hex_changed)
        top.addWidget(self._hex_edit, 1)
        outer.addLayout(top)

        # ---- Preset grid ----
        grid_label = QLabel("PRESETS")
        grid_label.setObjectName("SectionLabel")
        outer.addWidget(grid_label)

        grid_holder = QWidget()
        grid = QGridLayout(grid_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        cols = 6
        for i, color in enumerate(PRESETS):
            grid.addWidget(_Swatch(color, self._on_swatch), i // cols, i % cols)
        outer.addWidget(grid_holder)

        # ---- HSV sliders ----
        hsv_label = QLabel("HUE · SATURATION · VALUE")
        hsv_label.setObjectName("SectionLabel")
        outer.addWidget(hsv_label)

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)

        self._h_slider = QSlider(Qt.Horizontal)
        self._h_slider.setRange(0, 359)
        self._h_value = QLabel("0")
        form.addRow("Hue", self._row(self._h_slider, self._h_value))

        self._s_slider = QSlider(Qt.Horizontal)
        self._s_slider.setRange(0, 255)
        self._s_value = QLabel("0")
        form.addRow("Sat", self._row(self._s_slider, self._s_value))

        self._v_slider = QSlider(Qt.Horizontal)
        self._v_slider.setRange(0, 255)
        self._v_value = QLabel("0")
        form.addRow("Val", self._row(self._v_slider, self._v_value))

        for sl, lbl in (
            (self._h_slider, self._h_value),
            (self._s_slider, self._s_value),
            (self._v_slider, self._v_value),
        ):
            sl.valueChanged.connect(lambda v, l=lbl: l.setText(str(v)))
            sl.valueChanged.connect(self._on_hsv_changed)

        outer.addLayout(form)

        # ---- OK/Cancel ----
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        # Initial sync (sliders ← initial colour, preview painted)
        self._sync_sliders_from_color()
        self._refresh_preview()

    # ------------------------------------------------------------------ API
    @property
    def color(self) -> str:
        return self._color

    # --------------------------------------------------------------- inputs
    def _on_swatch(self, hex_str: str) -> None:
        self._color = _normalise(hex_str)
        self._sync_hex_from_color()
        self._sync_sliders_from_color()
        self._refresh_preview()

    def _on_hex_changed(self, text: str) -> None:
        if self._suspend_sync:
            return
        if _is_valid_hex(text):
            self._color = _normalise(text)
            self._sync_sliders_from_color()
            self._refresh_preview()

    def _on_hsv_changed(self, _value: int) -> None:
        if self._suspend_sync:
            return
        q = QColor.fromHsv(
            self._h_slider.value(),
            self._s_slider.value(),
            self._v_slider.value(),
        )
        self._color = q.name()
        self._sync_hex_from_color()
        self._refresh_preview()

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _row(slider: QSlider, label: QLabel) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        slider.setMinimumWidth(220)
        row.addWidget(slider, 1)
        label.setMinimumWidth(32)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(label)
        return wrap

    def _sync_hex_from_color(self) -> None:
        self._suspend_sync = True
        try:
            self._hex_edit.setText(self._color)
        finally:
            self._suspend_sync = False

    def _sync_sliders_from_color(self) -> None:
        q = QColor(self._color)
        h, s, v, _ = q.getHsv()
        self._suspend_sync = True
        try:
            # Hue is -1 for achromatic colours (black / white / greys).
            # Keep the previous hue slider position so neighbouring picks
            # don't get reset to red.
            if h >= 0:
                self._h_slider.setValue(h)
                self._h_value.setText(str(h))
            self._s_slider.setValue(s)
            self._s_value.setText(str(s))
            self._v_slider.setValue(v)
            self._v_value.setText(str(v))
        finally:
            self._suspend_sync = False

    def _refresh_preview(self) -> None:
        self._preview.setStyleSheet(
            f"background-color: {self._color};"
            "border: 1px solid #45475a;"
            "border-radius: 6px;"
        )


def pick_color(initial: str = "#FFFFFF", parent: QWidget | None = None) -> Optional[str]:
    """Open the themed picker and return ``#rrggbb`` on accept, else ``None``."""
    dlg = ColorPickerDialog(initial, parent)
    if dlg.exec() == QDialog.Accepted:
        return dlg.color
    return None
