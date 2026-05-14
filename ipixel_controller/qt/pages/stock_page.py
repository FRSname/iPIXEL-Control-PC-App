"""Stock feature, ported to PySide6.

Reuses the framework-agnostic helpers ``format_stock_display`` and
``get_stock_color`` from :mod:`ipixel_controller.services.stock_service`.
Data is fetched directly from yfinance on a background thread (via
:class:`BackgroundFetcher`) so the legacy Tk-bound StockService doesn't
need to be imported.

Sprite-font rendering is deferred — uses built-in panel text only here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...services.sprite_font import SpriteFontService
from ...services.stock_service import format_stock_display, get_stock_color
from ..device_bridge import DeviceBridge
from ..fetcher import BackgroundFetcher
from ..sprite_sender import SpriteSender
from ..widgets import Card, ColorButton, SpriteFontPicker
from .base import Page


FORMATS = [
    ("Price + Change %", "price_change"),
    ("Price only", "price_only"),
    ("Ticker + Price", "ticker_price"),
    ("Full info", "full"),
]


def _fetch_stock(ticker: str) -> Dict[str, Any]:
    """Synchronous yfinance fetch — runs in a worker thread."""
    import yfinance as yf

    if not ticker:
        raise ValueError("Ticker symbol is required")
    info = yf.Ticker(ticker).info
    if not info:
        raise ValueError(f"No data found for {ticker}")
    price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("price")
    )
    if price is None:
        raise ValueError(f"Could not get price for {ticker}")
    prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
    change = (price - prev) if prev else 0.0
    change_pct = ((change / prev) * 100) if prev else 0.0
    return {
        "ticker": ticker.upper(),
        "name": info.get("shortName", ticker),
        "price": float(price),
        "change": float(change),
        "change_percent": float(change_pct),
        "previous_close": float(prev) if prev else None,
        "currency": info.get("currency", "USD"),
    }


class StockPage(Page):
    title = "Stock"
    subtitle = "Live prices via yfinance — no API key needed."
    feature_id = "stock"

    def __init__(self, device: DeviceBridge, config, fonts: SpriteFontService) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._fonts = fonts
        self._sender = SpriteSender(device, fonts, temp_basename="ipixel_stock.png")
        self._current: Optional[Dict[str, Any]] = None

        self._fetcher = BackgroundFetcher(_fetch_stock)
        self._fetcher.started.connect(lambda: self._set_status("Fetching…"))
        self._fetcher.succeeded.connect(self._on_data)
        self._fetcher.failed.connect(self._on_error)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        # ----- Ticker
        ticker_card = Card(title="Ticker")
        ticker_row = QHBoxLayout()
        self.ticker_edit = QLineEdit("AAPL")
        self.ticker_edit.returnPressed.connect(self._fetch)
        ticker_row.addWidget(self.ticker_edit, 1)
        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.clicked.connect(self._fetch)
        ticker_row.addWidget(self.fetch_btn)
        ticker_card.add_layout(ticker_row)

        self.status_label = QLabel("Enter a ticker and press Fetch.")
        self.status_label.setStyleSheet("color:#a6adc8;")
        ticker_card.add(self.status_label)
        self.content_layout().addWidget(ticker_card)

        # ----- Display options
        opt = Card(title="Display")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.format_combo = QComboBox()
        for label, _ in FORMATS:
            self.format_combo.addItem(label)
        form.addRow("Format", self.format_combo)

        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("Background"))
        self.bg_btn = ColorButton("#000000")
        col_row.addWidget(self.bg_btn)
        col_row.addStretch()
        form.addRow("Colours", col_row)

        self.auto_color_check = QCheckBox("Auto-colour (green up / red down)")
        self.auto_color_check.setChecked(True)
        form.addRow("", self.auto_color_check)

        opt.add_layout(form)
        self.content_layout().addWidget(opt)

        # ----- Sprite font
        font_card = Card(title="Sprite font")
        names = self._config.get_sprite_font_names()
        self.font_picker = SpriteFontPicker(
            font_names=names,
            use_sprite=bool(self._config.get_setting("stock_use_sprite_font", True)),
            font_name=self._config.get_setting("stock_sprite_font_name", names[0] if names else ""),
        )
        self.font_picker.changed.connect(self._on_font_change)
        font_card.add(self.font_picker)
        self.content_layout().addWidget(font_card)

        # ----- Auto-refresh
        ref_card = Card(title="Auto-refresh")
        ref_form = QFormLayout()
        self.refresh_check = QCheckBox("Refresh price automatically")
        ref_form.addRow("", self.refresh_check)
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(30, 600)
        self.refresh_interval.setSingleStep(30)
        self.refresh_interval.setValue(60)
        self.refresh_interval.setSuffix(" s")
        ref_form.addRow("Interval", self.refresh_interval)
        ref_card.add_layout(ref_form)
        self.content_layout().addWidget(ref_card)

        # ----- Actions
        row = QHBoxLayout()
        self.send_btn = QPushButton("Send to panel")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)

        stop_btn = QPushButton("Stop refresh")
        stop_btn.clicked.connect(self._stop_refresh)
        row.addWidget(stop_btn)

        save_btn = QPushButton("Save as preset")
        save_btn.clicked.connect(self._save_preset)
        row.addWidget(save_btn)
        row.addStretch()
        self.content_layout().addLayout(row)

        self.on_connection_changed(self._device.is_connected)

    # ----------------------------------------------------------- status helpers
    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # ----------------------------------------------------------------- fetch
    def _fetch(self) -> None:
        ticker = self.ticker_edit.text().strip().upper()
        if not ticker:
            QMessageBox.warning(self, "No ticker", "Please enter a ticker.")
            return
        self.fetch_btn.setEnabled(False)
        self._fetcher.run(ticker=ticker)

    def _on_data(self, data) -> None:
        self.fetch_btn.setEnabled(True)
        self._current = data
        sign = "+" if data.get("change", 0) >= 0 else ""
        self._set_status(
            f"{data['ticker']}: ${data['price']:.2f}  "
            f"({sign}{data['change_percent']:.2f}%)"
        )

    def _on_error(self, error: str) -> None:
        self.fetch_btn.setEnabled(True)
        self._set_status(f"Error: {error}")

    # ------------------------------------------------------------------ send
    def _format_key(self) -> str:
        return FORMATS[self.format_combo.currentIndex()][1]

    def _send(self) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return
        if not self._current:
            QMessageBox.warning(self, "No data", "Fetch a ticker first.")
            return
        text = format_stock_display(self._current, self._format_key())
        color = (
            get_stock_color(self._current)
            if self.auto_color_check.isChecked()
            else "#FFFFFF"
        )
        self._sender.stop()
        if self.font_picker.use_sprite and self.font_picker.font_name:
            err = self._sender.send_static(
                text, self.font_picker.font_name, self.bg_btn.color
            )
            if err:
                QMessageBox.critical(self, "Sprite font error", err)
        else:
            self._device.send_text(
                text,
                char_height=16,
                color=color,
                bg_color=self.bg_btn.color,
                animation=0,
                speed=50,
            )
        if self.refresh_check.isChecked():
            self._refresh_timer.start(self.refresh_interval.value() * 1000)

    def _on_font_change(self) -> None:
        self._config.set_setting("stock_use_sprite_font", self.font_picker.use_sprite)
        self._config.set_setting("stock_sprite_font_name", self.font_picker.font_name)

    def refresh_font_list(self, names) -> None:
        self.font_picker.set_fonts(names)

    def _auto_refresh(self) -> None:
        ticker = self.ticker_edit.text().strip().upper()
        if not ticker:
            return
        # Chain fetch -> send via a one-shot connection
        def once(data):
            self._on_data(data)
            self._send()
            try:
                self._fetcher.succeeded.disconnect(once)
            except Exception:
                pass

        self._fetcher.succeeded.connect(once)
        self._fetcher.run(ticker=ticker)

    def _stop_refresh(self) -> None:
        self._refresh_timer.stop()

    # ---------------------------------------------------------------- preset
    def _save_preset(self) -> None:
        if not self._current:
            QMessageBox.warning(self, "No data", "Fetch a ticker first.")
            return
        default = f"Stock - {self._current['ticker']}"
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=default)
        if not ok or not name.strip():
            return
        preset = {
            "name": name.strip(),
            "type": self.feature_id,
            "ticker": self.ticker_edit.text().strip().upper(),
            "format": self._format_key(),
            "bg_color": self.bg_btn.color,
            "auto_color": self.auto_color_check.isChecked(),
            "auto_refresh": self.refresh_check.isChecked(),
            "refresh_interval": self.refresh_interval.value(),
        }
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        self.ticker_edit.setText(preset.get("ticker", "AAPL"))
        fmt = preset.get("format", "price_change")
        for i, (_, key) in enumerate(FORMATS):
            if key == fmt:
                self.format_combo.setCurrentIndex(i)
                break
        self.bg_btn.set_color(preset.get("bg_color", "#000000"))
        self.auto_color_check.setChecked(bool(preset.get("auto_color", True)))
        self.refresh_check.setChecked(bool(preset.get("auto_refresh", False)))
        self.refresh_interval.setValue(int(preset.get("refresh_interval", 60)))

        # Chain fetch -> send
        def once(_data):
            self._send()
            try:
                self._fetcher.succeeded.disconnect(once)
            except Exception:
                pass

        self._fetcher.succeeded.connect(once)
        self._fetch()
        return True

    # ----------------------------------------------------------------- state
    def on_connection_changed(self, connected: bool) -> None:
        self.send_btn.setEnabled(connected)
        if not connected:
            self._refresh_timer.stop()
