"""Main application window: sidebar nav + content stack + connection bar."""

from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
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
    HomePage,
    ImagePage,
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
}

NAV_FEATURES = [
    ("home", "Home", "🏠"),
    ("text", "Text", "📝"),
    ("image", "Image", "🖼"),
    ("clock", "Clock", "🕐"),
    ("stock", "Stock", "📈"),
    ("youtube", "YouTube", "📺"),
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

        # ---- Build pages ----
        self.pages: Dict[str, Page] = {}
        self._build_pages()
        self._build_sidebar()

        # ---- Hook device events for page-level reactions ----
        self._device.connected.connect(self._on_connected)
        self._device.disconnected.connect(self._on_disconnected)
        self._device.operation_failed.connect(self._on_operation_failed)
        self._device.connection_failed.connect(self._on_operation_failed)
        self._device.scan_failed.connect(self._on_operation_failed)

        # Initial page
        self.sidebar.select("home")
        self._show("home")

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
        self._add_page("weather", WeatherPage(self._device, self._config, self._fonts))
        self._add_page("animation", AnimationPage(self._device, self._config))

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

    def _on_disconnected(self) -> None:
        for p in self.pages.values():
            p.on_connection_changed(False)

    def _on_operation_failed(self, error: str) -> None:
        QMessageBox.critical(self, "Error", error)

    # --------------------------------------------------------------- presets
    def _run_preset(self, preset: dict) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(
                self, "Not connected", "Connect to a device first."
            )
            return
        ptype = preset.get("type")
        page = self.pages.get(ptype)
        if page and hasattr(page, "execute_preset"):
            self._show(ptype)
            page.execute_preset(preset)
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
