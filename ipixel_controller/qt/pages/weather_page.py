"""Weather feature, ported to PySide6.

Fetches from OpenWeatherMap directly (background thread + BackgroundFetcher).
The API key is read from / written to ``ipixel_secrets.json`` via the
shared :class:`ConfigManager`, so it persists across sessions.

Reuses ``format_weather_display`` from
:mod:`ipixel_controller.services.weather_service` for label formatting.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
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
from ...services.weather_service import format_weather_display
from ..device_bridge import DeviceBridge
from ..fetcher import BackgroundFetcher
from ..sprite_sender import SpriteSender
from ..widgets import Card, ColorButton, SpriteFontPicker
from .base import Page


FORMATS = [
    ("Temp + Condition", "temp_condition"),
    ("Temp only", "temp_only"),
    ("City + Temp", "city_temp"),
    ("Full", "full"),
]


def _fetch_weather(api_key: str, location: str, units: str) -> Dict[str, Any]:
    import requests

    if not api_key:
        raise ValueError("OpenWeatherMap API key required. Save it under Settings.")
    if not location:
        raise ValueError("Location is required.")
    params = {"q": location, "appid": api_key, "units": units}
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params=params,
        timeout=10,
    )
    if r.status_code == 401:
        raise ValueError("Invalid API key")
    if r.status_code == 404:
        raise ValueError(f"Location not found: {location}")
    if r.status_code != 200:
        raise ValueError(f"API error: {r.status_code}")
    data = r.json()
    main = data.get("main", {})
    weather = (data.get("weather") or [{}])[0]
    return {
        "location": data.get("name", location),
        "country": data.get("sys", {}).get("country", ""),
        "temperature": round(main.get("temp", 0)),
        "feels_like": round(main.get("feels_like", 0)),
        "condition": weather.get("main", "Unknown"),
        "description": weather.get("description", ""),
        "icon": weather.get("icon", ""),
        "units": units,
        "temp_unit": "°C" if units == "metric" else "°F",
    }


class WeatherPage(Page):
    title = "Weather"
    subtitle = "Live weather via OpenWeatherMap. Needs a free API key."
    feature_id = "weather"

    def __init__(self, device: DeviceBridge, config, fonts: SpriteFontService) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._fonts = fonts
        self._sender = SpriteSender(device, fonts, temp_basename="ipixel_weather.png")
        self._current: Optional[Dict[str, Any]] = None

        self._fetcher = BackgroundFetcher(_fetch_weather)
        self._fetcher.started.connect(lambda: self._set_status("Fetching…"))
        self._fetcher.succeeded.connect(self._on_data)
        self._fetcher.failed.connect(self._on_error)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        # ----- API key
        api_card = Card(title="API key")
        api_row = QHBoxLayout()
        self.api_edit = QLineEdit(self._config.get_secret("weather_api_key", ""))
        self.api_edit.setEchoMode(QLineEdit.Password)
        api_row.addWidget(self.api_edit, 1)
        save_key_btn = QPushButton("Save")
        save_key_btn.clicked.connect(self._save_api_key)
        api_row.addWidget(save_key_btn)
        api_card.add_layout(api_row)
        api_card.add(QLabel(
            "Get a free key from openweathermap.org → API keys."
        ))
        self.content_layout().addWidget(api_card)

        # ----- Location + units
        loc_card = Card(title="Location")
        form = QFormLayout()
        self.city_edit = QLineEdit(self._config.get_setting("weather_last_city", "London"))
        self.city_edit.returnPressed.connect(self._fetch)
        form.addRow("City", self.city_edit)

        self.units_combo = QComboBox()
        self.units_combo.addItems(["°C  (metric)", "°F  (imperial)"])
        last_units = self._config.get_setting("weather_units", "metric")
        self.units_combo.setCurrentIndex(0 if last_units == "metric" else 1)
        form.addRow("Units", self.units_combo)

        loc_card.add_layout(form)
        loc_row = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.clicked.connect(self._fetch)
        loc_row.addWidget(self.fetch_btn)
        loc_row.addStretch()
        loc_card.add_layout(loc_row)

        self.status_label = QLabel("Enter a city and fetch.")
        self.status_label.setStyleSheet("color:#a6adc8;")
        loc_card.add(self.status_label)

        self.content_layout().addWidget(loc_card)

        # ----- Display
        disp = Card(title="Display")
        dform = QFormLayout()
        self.format_combo = QComboBox()
        for label, _ in FORMATS:
            self.format_combo.addItem(label)
        dform.addRow("Format", self.format_combo)

        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("Text"))
        self.text_color = ColorButton("#FFFFFF")
        col_row.addWidget(self.text_color)
        col_row.addSpacing(16)
        col_row.addWidget(QLabel("Background"))
        self.bg_color = ColorButton("#000000")
        col_row.addWidget(self.bg_color)
        col_row.addStretch()
        dform.addRow("Colours", col_row)
        disp.add_layout(dform)
        self.content_layout().addWidget(disp)

        # ----- Sprite font
        font_card = Card(title="Sprite font")
        names = self._config.get_sprite_font_names()
        self.font_picker = SpriteFontPicker(
            font_names=names,
            use_sprite=bool(self._config.get_setting("weather_use_sprite_font", False)),
            font_name=self._config.get_setting("weather_sprite_font_name", names[0] if names else ""),
        )
        self.font_picker.changed.connect(self._on_font_change)
        font_card.add(self.font_picker)
        self.content_layout().addWidget(font_card)

        # ----- Refresh
        ref = Card(title="Auto-refresh")
        from PySide6.QtWidgets import QCheckBox

        self.refresh_check = QCheckBox("Refresh weather automatically")
        ref.add(self.refresh_check)
        rform = QFormLayout()
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(60, 3600)
        self.refresh_interval.setSingleStep(60)
        self.refresh_interval.setValue(600)
        self.refresh_interval.setSuffix(" s")
        rform.addRow("Interval", self.refresh_interval)
        ref.add_layout(rform)
        self.content_layout().addWidget(ref)

        # ----- Actions
        row = QHBoxLayout()
        self.send_btn = QPushButton("Send to panel")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)

        stop_btn = QPushButton("Stop refresh")
        stop_btn.clicked.connect(self._refresh_timer.stop)
        row.addWidget(stop_btn)

        save_btn = QPushButton("Save as preset")
        save_btn.clicked.connect(self._save_preset)
        row.addWidget(save_btn)
        row.addStretch()
        self.content_layout().addLayout(row)

        self.on_connection_changed(self._device.is_connected)

    # ----------------------------------------------------------------- helpers
    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _save_api_key(self) -> None:
        self._config.set_secret("weather_api_key", self.api_edit.text().strip())
        QMessageBox.information(self, "Saved", "API key saved.")

    def _units(self) -> str:
        return "metric" if self.units_combo.currentIndex() == 0 else "imperial"

    def _format_key(self) -> str:
        return FORMATS[self.format_combo.currentIndex()][1]

    # ------------------------------------------------------------------ fetch
    def _fetch(self) -> None:
        city = self.city_edit.text().strip()
        if not city:
            QMessageBox.warning(self, "No city", "Please enter a city.")
            return
        self._config.set_setting("weather_last_city", city)
        self._config.set_setting("weather_units", self._units())
        self.fetch_btn.setEnabled(False)
        self._fetcher.run(
            api_key=self.api_edit.text().strip(),
            location=city,
            units=self._units(),
        )

    def _on_data(self, data: Dict[str, Any]) -> None:
        self.fetch_btn.setEnabled(True)
        self._current = data
        self._set_status(
            f"{data['location']}: {data['temperature']}{data['temp_unit']}  "
            f"{data['condition']}"
        )

    def _on_error(self, error: str) -> None:
        self.fetch_btn.setEnabled(True)
        self._set_status(f"Error: {error}")

    # ------------------------------------------------------------------ send
    def _send(self) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return
        if not self._current:
            QMessageBox.warning(self, "No data", "Fetch weather first.")
            return
        text = format_weather_display(self._current, self._format_key())
        self._sender.stop()
        if self.font_picker.use_sprite and self.font_picker.font_name:
            err = self._sender.send_static(
                text, self.font_picker.font_name, self.bg_color.color
            )
            if err:
                QMessageBox.critical(self, "Sprite font error", err)
        else:
            self._device.send_text(
                text,
                char_height=16,
                color=self.text_color.color,
                bg_color=self.bg_color.color,
                animation=0,
                speed=50,
            )
        if self.refresh_check.isChecked():
            self._refresh_timer.start(self.refresh_interval.value() * 1000)

    def _on_font_change(self) -> None:
        self._config.set_setting("weather_use_sprite_font", self.font_picker.use_sprite)
        self._config.set_setting("weather_sprite_font_name", self.font_picker.font_name)

    def refresh_font_list(self, names) -> None:
        self.font_picker.set_fonts(names)

    def _auto_refresh(self) -> None:
        def once(_data):
            self._send()
            try:
                self._fetcher.succeeded.disconnect(once)
            except Exception:
                pass

        self._fetcher.succeeded.connect(once)
        self._fetch()

    # ---------------------------------------------------------------- preset
    def _save_preset(self) -> None:
        if not self._current:
            QMessageBox.warning(self, "No data", "Fetch weather first.")
            return
        default = f"Weather - {self._current.get('location', 'City')}"
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=default)
        if not ok or not name.strip():
            return
        preset = {
            "name": name.strip(),
            "type": self.feature_id,
            "city": self.city_edit.text().strip(),
            "units": self._units(),
            "format": self._format_key(),
            "text_color": self.text_color.color,
            "bg_color": self.bg_color.color,
            "auto_refresh": self.refresh_check.isChecked(),
            "refresh_interval": self.refresh_interval.value(),
        }
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        self.city_edit.setText(preset.get("city", "London"))
        self.units_combo.setCurrentIndex(0 if preset.get("units", "metric") == "metric" else 1)
        fmt = preset.get("format", "temp_condition")
        for i, (_, key) in enumerate(FORMATS):
            if key == fmt:
                self.format_combo.setCurrentIndex(i)
                break
        self.text_color.set_color(preset.get("text_color", "#FFFFFF"))
        self.bg_color.set_color(preset.get("bg_color", "#000000"))
        self.refresh_check.setChecked(bool(preset.get("auto_refresh", False)))
        self.refresh_interval.setValue(int(preset.get("refresh_interval", 600)))

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
