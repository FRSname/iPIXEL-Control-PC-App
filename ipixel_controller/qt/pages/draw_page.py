"""Embedded pixel-art editor (pixilart.com/draw).

The page tries to embed the site in a ``QWebEngineView`` so users never
leave the app. ``QtWebEngineWidgets`` is an optional Qt module (``pip
install PySide6-Addons`` or ``PySide6-WebEngine`` depending on platform);
if it isn't available we fall back to a button that opens the site in
the system browser plus a one-line note on how to install the embed.

Workflow either way:
1. Draw your sprite on Pixilart.
2. Use Pixilart's *Save / Download* to save a PNG to disk.
3. Switch to the *Image* tab and load it — or use *Image → Save as
   preset* if it should appear on the Home page.
"""

from __future__ import annotations

import webbrowser
from typing import Callable, Optional

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..widgets import Card
from .base import Page


PIXILART_URL = "https://www.pixilart.com/draw"


# Detect QtWebEngine at import time — keeps the rest of the module simple.
try:
    from PySide6.QtWebEngineCore import QWebEnginePage  # type: ignore
    from PySide6.QtWebEngineWidgets import QWebEngineView  # type: ignore

    _WEBENGINE_AVAILABLE = True
    _WEBENGINE_ERROR: Optional[str] = None

    class _QuietWebPage(QWebEnginePage):
        """A QWebEnginePage that swallows site-level JS console output.

        Pixilart's own JavaScript emits a few harmless console warnings
        (e.g. "#000 does not conform to #rrggbb"; "ramp is not defined")
        that otherwise stream into the parent process's terminal. None of
        them affect the editor — suppress to keep our output clean.
        """

        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
            return None
except Exception as e:  # pragma: no cover - depends on optional pkg
    QWebEnginePage = None  # type: ignore[assignment,misc]
    QWebEngineView = None  # type: ignore[assignment,misc]
    _QuietWebPage = None  # type: ignore[assignment,misc]
    _WEBENGINE_AVAILABLE = False
    _WEBENGINE_ERROR = str(e)


class DrawPage(Page):
    title = "Draw"
    subtitle = (
        "Draw a pixel sprite without leaving the app, then save the PNG "
        "and load it from the Image tab."
    )
    feature_id = "draw"

    def __init__(self, on_open_image: Optional[Callable[[], None]] = None) -> None:
        super().__init__()
        self._on_open_image = on_open_image

        # Action row — same in both modes
        actions = QHBoxLayout()
        open_browser_btn = QPushButton("Open in default browser")
        open_browser_btn.clicked.connect(lambda: webbrowser.open(PIXILART_URL))
        actions.addWidget(open_browser_btn)

        if on_open_image is not None:
            go_image_btn = QPushButton("Go to Image tab")
            go_image_btn.clicked.connect(lambda: on_open_image())
            actions.addWidget(go_image_btn)

        actions.addStretch()
        self.content_layout().addLayout(actions)

        if _WEBENGINE_AVAILABLE:
            self._build_embedded()
        else:
            self._build_fallback()

    # --------------------------------------------------------------- embed
    def _build_embedded(self) -> None:
        assert QWebEngineView is not None
        self._view = QWebEngineView()
        # Use the quiet page so pixilart's JS warnings stay out of the
        # parent process's terminal.
        if _QuietWebPage is not None:
            self._view.setPage(_QuietWebPage(self._view))
        self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._view.setMinimumHeight(420)
        self._view.load(QUrl(PIXILART_URL))

        # Browser-style nav above the view so the actions row at the top
        # stays focused on Open-in-browser / Go to Image.
        nav = QHBoxLayout()
        back_btn = QPushButton("←")
        back_btn.setMaximumWidth(40)
        back_btn.clicked.connect(self._view.back)
        nav.addWidget(back_btn)

        fwd_btn = QPushButton("→")
        fwd_btn.setMaximumWidth(40)
        fwd_btn.clicked.connect(self._view.forward)
        nav.addWidget(fwd_btn)

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self._view.reload)
        nav.addWidget(reload_btn)

        nav.addStretch()
        self.content_layout().addLayout(nav)

        # The webview should consume every remaining pixel below the
        # action and nav rows.
        self.take_remaining_space(self._view)

    # ------------------------------------------------------------- fallback
    def _build_fallback(self) -> None:
        card = Card(title="Embedded view unavailable")
        msg = QLabel(
            "To embed the Pixilart editor directly in this window, install "
            "Qt's WebEngine module:\n\n"
            "    python -m pip install PySide6-Addons\n\n"
            "Then restart the app. Until then, use the button above to open "
            "the editor in your default browser. Once you've saved your PNG, "
            "load it from the Image tab."
        )
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card.add(msg)
        if _WEBENGINE_ERROR:
            err = QLabel(f"Import error: {_WEBENGINE_ERROR}")
            err.setStyleSheet("color:#6c7086;")
            err.setWordWrap(True)
            card.add(err)
        self.content_layout().addWidget(card)
