"""A fallback page for features not yet ported to Qt.

While the migration is in progress these pages explain to the user what
they can do today (continue using the legacy Tkinter app) and what is
coming. They keep the new UI navigable without claiming features that
don't exist yet.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QVBoxLayout

from ..widgets import Card
from .base import Page


class PlaceholderPage(Page):
    def __init__(self, feature_id: str, display_name: str, description: str = "") -> None:
        self.title = display_name
        self.subtitle = "This feature hasn't been ported to the new UI yet."
        super().__init__()

        card = Card(title="Migration in progress")
        body = QLabel(
            description
            or "This page is part of the ongoing PySide6 rewrite. The feature "
            "still works in the legacy Tkinter UI — open it from there until "
            "the new view is ready."
        )
        body.setWordWrap(True)
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card.add(body)

        hint = QLabel(
            f"Feature id: <code>{feature_id}</code>"
        )
        hint.setTextFormat(Qt.RichText)
        hint.setStyleSheet("color:#6c7086;")
        card.add(hint)

        self.content_layout().addWidget(card)
