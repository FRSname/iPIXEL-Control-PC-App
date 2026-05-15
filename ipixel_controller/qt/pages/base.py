"""Shared base class for content pages.

Every page gets a header + subheader and a content area. Pages can react
to connection state changes by overriding :meth:`on_connection_changed`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class Page(QWidget):
    title: str = "Page"
    subtitle: str = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContentArea")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(6)

        header = QLabel(self.title)
        header.setObjectName("PageHeader")
        outer.addWidget(header)

        if self.subtitle:
            sub = QLabel(self.subtitle)
            sub.setObjectName("PageSubheader")
            sub.setWordWrap(True)
            outer.addWidget(sub)

        outer.addSpacing(14)

        self._content = QVBoxLayout()
        self._content.setSpacing(14)
        outer.addLayout(self._content)
        # Trailing stretch keeps cards top-anchored on pages with only
        # fixed-height content. Pages that need to fill the window (e.g.
        # the embedded Draw view) call :meth:`take_remaining_space` to
        # claim it instead.
        self._trailing_stretch_index = outer.count()
        outer.addStretch()

        self._outer = outer

    def content_layout(self) -> QVBoxLayout:
        return self._content

    def take_remaining_space(self, widget: QWidget) -> None:
        """Drop the trailing spacer and let ``widget`` fill the rest.

        Useful for pages whose main content (a webview, a large preview)
        should grow to use every available pixel below the header.
        """
        # Remove the spacer at the recorded index.
        item = self._outer.takeAt(self._trailing_stretch_index)
        if item is not None:
            # Spacer items don't own widgets; nothing to delete.
            del item
        self._outer.addWidget(widget, 1)

    def on_connection_changed(self, connected: bool) -> None:
        """Override in subclasses to react to connection events."""

    def on_shown(self) -> None:
        """Called whenever the page becomes visible."""

    def on_hidden(self) -> None:
        """Called whenever the page is being navigated away from."""
