"""A simple rounded card frame used for grouping content on a page."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class Card(QFrame):
    """Rounded surface with optional header label.

    Cards hug their content vertically. Without ``Maximum`` on the
    vertical size policy, putting a card inside a :class:`QStackedWidget`
    (e.g. Clock's mode subviews) lets the card inherit the stack's
    height, leaving a large empty gap at the bottom.
    """

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 16)
        self._layout.setSpacing(10)

        if title:
            label = QLabel(title.upper())
            label.setObjectName("SectionLabel")
            self._layout.addWidget(label)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def body_layout(self) -> QVBoxLayout:
        return self._layout
