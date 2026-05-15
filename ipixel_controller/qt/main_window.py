"""Main application window: sidebar nav + content stack + connection bar."""

from __future__ import annotations

from typing import Dict

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.config import ConfigManager
from ..core.events import EventBus
from ..services.sprite_font import SpriteFontService
from .device_bridge import DeviceBridge
from .pages import (
    AnimationPage,
    ClockPage,
    DrawPage,
    HomePage,
    ImagePage,
    InstagramPage,
    Page,
    PlaceholderPage,
    SettingsPage,
    StockPage,
    TextPage,
    WeatherPage,
    YoutubePage,
)
from .widgets import ConnectionBar, Sidebar


# Feature list: id, label, icon, factory(device, config) -> Page
PORTED_FEATURES = {
    "text",
    "image",
    "clock",
    "animation",
    "stock",
    "weather",
    "youtube",
    "instagram",
    "draw",
}

NAV_FEATURES = [
    ("home", "Home", "🏠"),
    ("text", "Text", "📝"),
    ("image", "Image", "🖼"),
    ("draw", "Draw", "✏"),
    ("clock", "Clock", "🕐"),
    ("stock", "Stock", "📈"),
    ("youtube", "YouTube", "📺"),
    ("instagram", "Instagram", "📷"),
    ("weather", "Weather", "🌤"),
    ("animation", "Animations", "🎨"),
    ("settings", "Settings", "⚙"),
]


class MainWindow(QMainWindow):
    def __init__(self, config: ConfigManager, events: EventBus) -> None:
        super().__init__()
        self.setWindowTitle("iPixel Controller")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        self._config = config
        self._events = events
        self._device = DeviceBridge()

        # The page whose live updates are currently driving the panel —
        # set whenever a preset is executed (manual or via playlist). Used
        # to stop the previous page's timers when the playlist advances
        # without switching the visible page.
        self._active_preset_page: Page | None = None

        # Sprite-font service is shared across every text-based page so
        # they can render via custom fonts and use real background colours.
        self._fonts = SpriteFontService()
        self._fonts.register_fonts_from_settings(self._config.get_sprite_fonts())

        # ---- Layout ----
        central = QWidget()
        central.setObjectName("ContentArea")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.connection_bar = ConnectionBar(self._device)
        right.addWidget(self.connection_bar)

        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)

        right_holder = QWidget()
        right_holder.setObjectName("ContentArea")
        right_holder.setLayout(right)
        root.addWidget(right_holder, 1)

        # ---- Status bar ----
        # Non-modal area to surface BLE errors without spamming dialogs
        # (a playlist cycling through dead-link presets would otherwise
        # produce one modal per item).
        self._status_bar = QStatusBar()
        self._status_bar.setSizeGripEnabled(False)
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color:#a6adc8;")
        self._status_bar.addWidget(self._status_label, 1)
        self.setStatusBar(self._status_bar)

        # Auto-clear the status text after a few seconds of quiet.
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        self._status_clear_timer.timeout.connect(
            lambda: self._set_status("Ready", "neutral")
        )

        # Track consecutive "no ack" failures to detect a dead BLE link.
        self._consecutive_link_errors = 0
        self._last_error_text: str = ""
        self._last_error_time: float = 0.0

        # ---- Build pages ----
        self.pages: Dict[str, Page] = {}
        self._build_pages()
        self._build_sidebar()

        # ---- Hook device events for page-level reactions ----
        self._device.connected.connect(self._on_connected)
        self._device.disconnected.connect(self._on_disconnected)
        self._device.operation_failed.connect(self._on_operation_failed)
        self._device.connection_failed.connect(self._on_connection_failed)
        self._device.scan_failed.connect(self._on_scan_failed)

        # Initial page
        self.sidebar.select("home")
        self._show("home")

        # Optionally reconnect to the last-known device after the event
        # loop is running — defer 600 ms so the BLE thread is ready and
        # the UI is painted first.
        if self._config.get_setting("auto_connect", True):
            last = self._config.get_setting("last_device")
            if last:
                QTimer.singleShot(600, lambda: self._auto_connect(last))

    def _auto_connect(self, address: str) -> None:
        """Reconnect to the last-used device without requiring a scan."""
        # Surface the address in the dropdown so the user can see what's
        # being reused, even though we connect directly.
        self.connection_bar.device_combo.addItem(f"Last device ({address})", address)
        self.connection_bar.device_combo.setCurrentIndex(
            self.connection_bar.device_combo.count() - 1
        )
        self._device.connect(address)

    # ------------------------------------------------------------ page setup
    def _build_pages(self) -> None:
        # Home
        home = HomePage(
            self._config,
            on_run_preset=self._run_preset,
            on_open_text=lambda: self._show("text"),
        )
        self._add_page("home", home)

        # Ported feature pages
        self._add_page("text", TextPage(self._device, self._config, self._fonts))
        self._add_page("image", ImagePage(self._device, self._config))
        self._add_page("clock", ClockPage(self._device, self._config, self._fonts))
        self._add_page("stock", StockPage(self._device, self._config, self._fonts))
        self._add_page("youtube", YoutubePage(self._device, self._config, self._fonts))
        self._add_page("instagram", InstagramPage(self._device, self._config, self._fonts))
        self._add_page("weather", WeatherPage(self._device, self._config, self._fonts))
        self._add_page("animation", AnimationPage(self._device, self._config))
        self._add_page("draw", DrawPage(on_open_image=lambda: self._show("image")))

        # Settings — pass fonts so the library editor can manage them.
        self._add_page(
            "settings",
            SettingsPage(
                self._device,
                self._config,
                self._fonts,
                on_fonts_changed=self._on_fonts_changed,
            ),
        )

        # Placeholders for anything still unported (none currently — kept
        # as a safety net in case NAV_FEATURES grows ahead of pages).
        for key, label, _ in NAV_FEATURES:
            if key in self.pages:
                continue
            self._add_page(key, PlaceholderPage(key, label))

    def _add_page(self, key: str, page: Page) -> None:
        self.pages[key] = page
        self.stack.addWidget(page)

    def _build_sidebar(self) -> None:
        self.sidebar.add_section("Navigate")
        for key, label, icon in NAV_FEATURES:
            if key == "settings":
                continue
            ported = key in PORTED_FEATURES or key == "home"
            btn = self.sidebar.add_item(key, label, icon)
            if not ported:
                btn.setToolTip("Not yet available in the new UI")
        self.sidebar.add_stretch()
        self.sidebar.add_item("settings", "Settings", "⚙")
        self.sidebar.selected.connect(self._show)

    # ----------------------------------------------------------------- pages
    def _show(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        current = self.stack.currentWidget()
        if isinstance(current, Page) and current is not page:
            current.on_hidden()
        self.stack.setCurrentWidget(page)
        self.sidebar.select(key)
        page.on_shown()

    # --------------------------------------------------------- font reload
    def _on_fonts_changed(self) -> None:
        """Settings page added/edited/deleted a sprite font."""
        fonts = self._config.get_sprite_fonts()
        # Replace the service's registry by recreating it — simpler than
        # diffing.
        self._fonts._fonts.clear()
        self._fonts.register_fonts_from_settings(fonts)
        # Notify pages that hold a SpriteFontPicker so they refresh.
        for page in self.pages.values():
            if hasattr(page, "refresh_font_list"):
                page.refresh_font_list([f.get("name", "") for f in fonts])

    # ----------------------------------------------------------------- bridge
    def _on_connected(self, _info) -> None:
        for p in self.pages.values():
            p.on_connection_changed(True)
        # Persist last device
        if self._device.device_info:
            self._config.set_setting("last_device", self._device.device_info.address)
        self._consecutive_link_errors = 0
        self._set_status("Connected", "ok")

    def _on_disconnected(self) -> None:
        for p in self.pages.values():
            p.on_connection_changed(False)
        self._consecutive_link_errors = 0
        self._set_status("Disconnected", "warn")

    def _on_operation_failed(self, error: str) -> None:
        """Surface a runtime BLE failure without blocking the UI.

        Repeated identical errors collapse into the status bar instead of
        stacking modals. If the link looks dead (several "no ack" errors
        in a row) we disconnect, which also stops the playlist and any
        page-level live timers.
        """
        # Deduplicate same-error storms — only update the text on change
        # or once a second.
        now = time.monotonic()
        if error == self._last_error_text and now - self._last_error_time < 1.0:
            return
        self._last_error_text = error
        self._last_error_time = now

        self._set_status(error, "error")

        # Detect dead-link patterns. pypixelcolor surfaces 'no ack from
        # device' / 'cur12k_no_answer' when writes time out.
        link_dead = any(
            token in error.lower()
            for token in ("no ack", "no_answer", "no answer", "timeout", "disconnect")
        )
        if link_dead:
            self._consecutive_link_errors += 1
            if self._consecutive_link_errors >= 2:
                # Disconnect — pages and the home-page playlist player
                # listen for the disconnect event and stop themselves.
                self._consecutive_link_errors = 0
                self._set_status(
                    "Lost connection to panel — disconnecting.", "error"
                )
                self._device.disconnect()
        else:
            self._consecutive_link_errors = 0

    def _on_connection_failed(self, error: str) -> None:
        """Connect attempt failed — show in status bar, no modal spam."""
        self._set_status(f"Connect failed: {error}", "error")

    def _on_scan_failed(self, error: str) -> None:
        self._set_status(f"Scan failed: {error}", "error")

    def _set_status(self, text: str, level: str = "neutral") -> None:
        color = {
            "neutral": "#a6adc8",
            "warn": "#f9e2af",
            "error": "#f38ba8",
            "ok": "#a6e3a1",
        }.get(level, "#a6adc8")
        self._status_label.setStyleSheet(f"color:{color};")
        self._status_label.setText(text)
        # Errors stay visible for 8s, everything else for 4s.
        self._status_clear_timer.start(8000 if level == "error" else 4000)

    # --------------------------------------------------------------- presets
    def _run_preset(self, preset: dict, switch_page: bool = True) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(
                self, "Not connected", "Connect to a device first."
            )
            return
        ptype = preset.get("type")
        page = self.pages.get(ptype)
        if page and hasattr(page, "execute_preset"):
            # Stop the previously-running preset's live updates so it
            # stops fighting the panel. _show() handles this implicitly
            # via on_hidden() when it swaps the visible page; when the
            # playlist advances silently (switch_page=False) the previous
            # page is never hidden, so we trigger the cleanup ourselves.
            if (
                self._active_preset_page is not None
                and self._active_preset_page is not page
            ):
                self._active_preset_page.on_hidden()
            if switch_page:
                self._show(ptype)
            page.execute_preset(preset)
            self._active_preset_page = page
        else:
            QMessageBox.information(
                self,
                "Preset not supported yet",
                f"Presets of type '{ptype}' will run once that feature is "
                "ported to the new UI. Use the legacy app in the meantime.",
            )

    # --------------------------------------------------------------- cleanup
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        try:
            self._device.disconnect()
        finally:
            super().closeEvent(event)
