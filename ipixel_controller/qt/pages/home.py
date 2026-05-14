"""Home page — preset grid and quick-launch surface.

The home page surfaces user-saved presets first. Tabs in the legacy UI
buried these behind a 'Control Board' tab; here they are the landing
view because that's what users open the app to do.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..widgets import Card
from .base import Page


TYPE_ICONS: Dict[str, str] = {
    "text": "T",
    "image": "I",
    "clock": "C",
    "stock": "$",
    "youtube": "Y",
    "weather": "W",
    "animation": "A",
    "teams": "M",
}


class _PresetTile(QPushButton):
    def __init__(self, preset: dict, on_run: Callable[[dict], None]) -> None:
        super().__init__()
        name = preset.get("name", "Preset")[:24]
        ptype = preset.get("type", "?")
        icon = TYPE_ICONS.get(ptype, "•")
        self.setText(f"{icon}   {name}")
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: on_run(preset))


class HomePage(Page):
    title = "Presets"
    subtitle = "Quick access to everything you've saved. Click to send to the panel."

    def __init__(
        self,
        config,
        on_run_preset: Callable[[dict], None],
        on_open_text: Callable[[], None],
    ) -> None:
        super().__init__()
        self._config = config
        self._on_run_preset = on_run_preset
        self._on_open_text = on_open_text

        # Quick actions row
        actions = Card(title="Quick actions")
        row = QHBoxLayout()
        row.setSpacing(8)

        new_text_btn = QPushButton("Send text")
        new_text_btn.setObjectName("PrimaryButton")
        new_text_btn.clicked.connect(lambda: on_open_text())
        row.addWidget(new_text_btn)

        refresh_btn = QPushButton("Refresh presets")
        refresh_btn.clicked.connect(self.refresh)
        row.addWidget(refresh_btn)
        row.addStretch()
        actions.add_layout(row)
        self.content_layout().addWidget(actions)

        # Presets card with scroll area
        self._presets_card = Card(title="Saved presets")

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setMinimumHeight(280)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._grid_host)
        self._presets_card.add(self._scroll)
        self.content_layout().addWidget(self._presets_card)

        self.refresh()

    def refresh(self) -> None:
        # Clear current grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        presets: List[dict] = self._config.get_presets()
        if not presets:
            empty = QLabel(
                "No presets yet. Open a feature, configure it, then click "
                "'Save as preset'."
            )
            empty.setWordWrap(True)
            empty.setStyleSheet("color:#6c7086; padding: 24px;")
            self._grid.addWidget(empty, 0, 0)
            return

        cols = 3
        for i, preset in enumerate(presets):
            tile = _PresetTile(preset, self._on_run_preset)
            self._grid.addWidget(tile, i // cols, i % cols)

    def on_shown(self) -> None:
        self.refresh()
