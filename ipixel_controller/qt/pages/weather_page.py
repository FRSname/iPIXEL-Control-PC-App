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

import os

from PIL import Image

from ...services.sprite_font import SpriteFontService
from ...services.weather_service import format_weather_display
from ...utils.image_utils import save_temp_image
from ...utils.paths import resolve_asset_path
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

LAYOUT_ICONS = "icons"
LAYOUT_TEXT = "text"
LAYOUTS = [
    ("Icons (weather icon + temp + °C + +/-)", LAYOUT_ICONS),
    ("Text only", LAYOUT_TEXT),
]


def _weather_icon_filename(condition: str, icon_code: str) -> str:
    """Map OWM condition + icon code to a file in Gallery/Sprites/."""
    cond = (condition or "").lower()
    if cond == "thunderstorm":
        return "Thunderstorm.png"
    if cond in ("drizzle", "rain"):
        return "Rainy.png"
    if cond == "snow":
        return "Snow.png"
    if cond in (
        "mist", "smoke", "haze", "dust", "fog", "sand", "ash", "squall", "tornado",
    ):
        return "Atmospheric.png"
    if cond == "clouds":
        # 02d/02n = few clouds; rest = broken/overcast.
        return "SunCloudy.png" if str(icon_code).startswith("02") else "Cloudy.png"
    if cond == "clear":
        return "Sunny.png"
    return "Cloudy.png"


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

        self.layout_combo = QComboBox()
        for label, _ in LAYOUTS:
            self.layout_combo.addItem(label)
        last_layout = self._config.get_setting("weather_layout", LAYOUT_ICONS)
        self.layout_combo.setCurrentIndex(
            0 if last_layout == LAYOUT_ICONS else 1
        )
        self.layout_combo.currentIndexChanged.connect(self._on_layout_change)
        dform.addRow("Layout", self.layout_combo)

        self.format_combo = QComboBox()
        for label, _ in FORMATS:
            self.format_combo.addItem(label)
        dform.addRow("Text format", self.format_combo)

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

        # Format combo only matters for the text layout — hide it when
        # the icons layout is selected.
        self._format_row_label = QLabel()  # tracking; real label is in form
        self._refresh_format_row_visibility()

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

        self._sender.stop()

        layout = LAYOUTS[self.layout_combo.currentIndex()][1]
        if layout == LAYOUT_ICONS:
            err = self._send_icon_layout()
            if err:
                QMessageBox.critical(self, "Weather icons", err)
        else:
            text = format_weather_display(self._current, self._format_key())
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

    # ------------------------------------------------------- icon composite
    def _send_icon_layout(self) -> Optional[str]:
        """Render the legacy 64×16 icon composite and dispatch it.

        Layout (left → right): condition icon (16×16), centred temperature
        number, °C glyph (4×16), Temp_plus / Temp_minus indicator on the
        far right (11×16).
        """
        data = self._current or {}
        condition = data.get("condition", "")
        icon_code = data.get("icon", "")
        temp = int(data.get("temperature", 0))

        bg = self.bg_color.color
        canvas = Image.new("RGB", (64, 16), bg)

        # 1) Condition icon, left edge.
        cond_path = resolve_asset_path(
            os.path.join("Gallery", "Sprites", _weather_icon_filename(condition, icon_code))
        )
        if os.path.isfile(cond_path):
            try:
                with Image.open(cond_path) as icon:
                    icon = icon.convert("RGBA")
                    if icon.size != (16, 16):
                        icon = icon.resize((16, 16), Image.LANCZOS)
                    canvas.paste(icon, (0, 0), icon)
            except Exception as e:  # noqa: BLE001
                return f"Failed to load condition icon: {e}"

        # 2) Temperature number — sprite font if enabled, plain fallback otherwise.
        available_start, available_end = 16, 53
        available_width = available_end - available_start

        temp_str = str(abs(temp))
        text_img: Optional[Image.Image] = None
        minus_img: Optional[Image.Image] = None

        if self.font_picker.use_sprite and self.font_picker.font_name:
            text_img, terr = self._fonts.render_text_line(
                temp_str, self.font_picker.font_name, bg
            )
            if terr:
                # Fall through — we'll still place the rest of the layout.
                text_img = None
            if temp < 0:
                minus_img, _err = self._fonts.render_text_line(
                    "-", self.font_picker.font_name, bg
                )

        text_w = text_img.width if text_img else len(temp_str) * 7
        minus_w = minus_img.width if minus_img else (7 if temp < 0 else 0)

        # 3) °C glyph (4×16) right after the number.
        celsius_img: Optional[Image.Image] = None
        celsius_w = 4
        celsius_path = resolve_asset_path(
            os.path.join("Gallery", "Sprites", "Celsius.png")
        )
        if os.path.isfile(celsius_path):
            try:
                celsius_img = Image.open(celsius_path).convert("RGBA")
                if celsius_img.size != (4, 16):
                    celsius_img = celsius_img.resize((4, 16), Image.LANCZOS)
                celsius_w = celsius_img.width
            except Exception:  # noqa: BLE001
                celsius_img = None

        spacing = 1
        content_w = text_w + spacing + celsius_w
        centered_start = available_start + (available_width - content_w) // 2

        if minus_img is not None and temp < 0:
            mx = centered_start - minus_w - 1
            my = (16 - minus_img.height) // 2
            canvas.paste(minus_img, (mx, my), minus_img if minus_img.mode == "RGBA" else None)

        if text_img is not None:
            ty = (16 - text_img.height) // 2
            canvas.paste(
                text_img, (centered_start, ty),
                text_img if text_img.mode == "RGBA" else None,
            )

        if celsius_img is not None:
            canvas.paste(celsius_img, (centered_start + text_w + spacing, 0), celsius_img)
            celsius_img.close()

        # 4) Right-edge +/- temperature indicator (11×16 at x=53).
        indicator = "Temp_plus.png" if temp >= 0 else "Temp_minus.png"
        ind_path = resolve_asset_path(os.path.join("Gallery", "Sprites", indicator))
        if os.path.isfile(ind_path):
            try:
                with Image.open(ind_path) as ind:
                    ind = ind.convert("RGBA")
                    if ind.size != (11, 16):
                        ind = ind.resize((11, 16), Image.LANCZOS)
                    canvas.paste(ind, (53, 0), ind)
            except Exception:  # noqa: BLE001
                pass

        path = save_temp_image(canvas, "ipixel_weather.png")
        self._device.send_image(path, resize_method="crop", save_slot=0)
        return None

    # --------------------------------------------------------------- options
    def _on_layout_change(self, _idx: int) -> None:
        layout = LAYOUTS[self.layout_combo.currentIndex()][1]
        self._config.set_setting("weather_layout", layout)
        self._refresh_format_row_visibility()

    def _refresh_format_row_visibility(self) -> None:
        # The format combo is only meaningful for the text layout.
        is_text = self.layout_combo.currentIndex() == 1
        self.format_combo.setEnabled(is_text)

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
            "layout": LAYOUTS[self.layout_combo.currentIndex()][1],
            "text_color": self.text_color.color,
            "bg_color": self.bg_color.color,
            "auto_refresh": self.refresh_check.isChecked(),
            "refresh_interval": self.refresh_interval.value(),
            "weather_use_sprite_font": self.font_picker.use_sprite,
            "weather_sprite_font_name": self.font_picker.font_name,
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
        layout = preset.get("layout", LAYOUT_ICONS)
        for i, (_, key) in enumerate(LAYOUTS):
            if key == layout:
                self.layout_combo.setCurrentIndex(i)
                break
        self.text_color.set_color(preset.get("text_color", "#FFFFFF"))
        self.bg_color.set_color(preset.get("bg_color", "#000000"))
        self.refresh_check.setChecked(bool(preset.get("auto_refresh", False)))
        self.refresh_interval.setValue(int(preset.get("refresh_interval", 600)))
        self.font_picker.set_use_sprite(bool(preset.get("weather_use_sprite_font", False)))
        self.font_picker.set_font_name(preset.get("weather_sprite_font_name", ""))

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
