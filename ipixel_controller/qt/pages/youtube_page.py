"""YouTube channel-stats feature, ported to PySide6.

Pulls subscriber + view counts from the YouTube Data API v3 in a worker
thread. API key persists in ``ipixel_secrets.json`` via ``ConfigManager``.
Inline-logo rendering is deferred (built-in panel text only for now).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer
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
)

from ...services.sprite_font import SpriteFontService
from ...services.youtube_service import format_youtube_display
from ..device_bridge import DeviceBridge
from ..fetcher import BackgroundFetcher
from ..sprite_sender import SpriteSender
from ..widgets import Card, ColorButton, SpriteFontPicker
from .base import Page


FORMATS = [
    ("Subscribers", "subscribers"),
    ("Subs + Views", "subs_views"),
    ("Channel + Subs", "channel_subs"),
]


def _fetch_youtube(api_key: str, channel: str) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("YouTube API key required. Save it under Settings.")
    if not channel:
        raise ValueError("Channel ID or @handle is required.")
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", developerKey=api_key)
    channel_id = channel
    if channel.startswith("@"):
        search = yt.search().list(
            part="snippet", q=channel, type="channel", maxResults=1
        ).execute()
        items = search.get("items") or []
        if not items:
            raise ValueError(f"Channel not found: {channel}")
        channel_id = items[0]["snippet"]["channelId"]

    resp = yt.channels().list(part="snippet,statistics", id=channel_id).execute()
    items = resp.get("items") or []
    if not items:
        raise ValueError(f"Channel not found: {channel_id}")
    snippet = items[0]["snippet"]
    stats = items[0]["statistics"]
    return {
        "channel_id": channel_id,
        "title": snippet.get("title", "Unknown"),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "view_count": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
    }


class YoutubePage(Page):
    title = "YouTube"
    subtitle = "Channel subscribers + views. Needs a YouTube Data API v3 key."
    feature_id = "youtube"

    def __init__(self, device: DeviceBridge, config, fonts: SpriteFontService) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._fonts = fonts
        self._sender = SpriteSender(device, fonts, temp_basename="ipixel_youtube.png")
        self._current: Optional[Dict[str, Any]] = None

        self._fetcher = BackgroundFetcher(_fetch_youtube)
        self._fetcher.started.connect(lambda: self._set_status("Fetching…"))
        self._fetcher.succeeded.connect(self._on_data)
        self._fetcher.failed.connect(self._on_error)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        # ---- API key
        api = Card(title="API key")
        api_row = QHBoxLayout()
        self.api_edit = QLineEdit(self._config.get_secret("youtube_api_key", ""))
        self.api_edit.setEchoMode(QLineEdit.Password)
        api_row.addWidget(self.api_edit, 1)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_key)
        api_row.addWidget(save_btn)
        api.add_layout(api_row)
        api.add(QLabel("Generate at console.cloud.google.com → YouTube Data API v3."))
        self.content_layout().addWidget(api)

        # ---- Channel
        ch = Card(title="Channel")
        ch_row = QHBoxLayout()
        self.channel_edit = QLineEdit(
            self._config.get_setting("youtube_last_channel", "@MrBeast")
        )
        self.channel_edit.returnPressed.connect(self._fetch)
        ch_row.addWidget(self.channel_edit, 1)
        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.clicked.connect(self._fetch)
        ch_row.addWidget(self.fetch_btn)
        ch.add_layout(ch_row)
        self.status_label = QLabel("Channel ID or @handle, then Fetch.")
        self.status_label.setStyleSheet("color:#a6adc8;")
        ch.add(self.status_label)
        self.content_layout().addWidget(ch)

        # ---- Display
        disp = Card(title="Display")
        form = QFormLayout()
        self.format_combo = QComboBox()
        for label, _ in FORMATS:
            self.format_combo.addItem(label)
        form.addRow("Format", self.format_combo)

        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("Text"))
        self.text_color = ColorButton("#FFFFFF")
        col_row.addWidget(self.text_color)
        col_row.addSpacing(16)
        col_row.addWidget(QLabel("Background"))
        self.bg_color = ColorButton("#000000")
        col_row.addWidget(self.bg_color)
        col_row.addStretch()
        form.addRow("Colours", col_row)
        disp.add_layout(form)
        self.content_layout().addWidget(disp)

        # ---- Sprite font
        font_card = Card(title="Sprite font")
        names = self._config.get_sprite_font_names()
        self.font_picker = SpriteFontPicker(
            font_names=names,
            use_sprite=bool(self._config.get_setting("youtube_use_sprite_font", True)),
            font_name=self._config.get_setting("youtube_sprite_font_name", names[0] if names else ""),
        )
        self.font_picker.changed.connect(self._on_font_change)
        font_card.add(self.font_picker)
        self.content_layout().addWidget(font_card)

        # ---- Auto-refresh
        ref = Card(title="Auto-refresh")
        self.refresh_check = QCheckBox("Refresh subscriber count automatically")
        ref.add(self.refresh_check)
        rform = QFormLayout()
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(60, 3600)
        self.refresh_interval.setSingleStep(60)
        self.refresh_interval.setValue(300)
        self.refresh_interval.setSuffix(" s")
        rform.addRow("Interval", self.refresh_interval)
        ref.add_layout(rform)
        self.content_layout().addWidget(ref)

        # ---- Actions
        row = QHBoxLayout()
        self.send_btn = QPushButton("Send to panel")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)

        stop_btn = QPushButton("Stop refresh")
        stop_btn.clicked.connect(self._refresh_timer.stop)
        row.addWidget(stop_btn)

        save_preset_btn = QPushButton("Save as preset")
        save_preset_btn.clicked.connect(self._save_preset)
        row.addWidget(save_preset_btn)
        row.addStretch()
        self.content_layout().addLayout(row)

        self.on_connection_changed(self._device.is_connected)

    # ---------------------------------------------------------------- helpers
    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _save_key(self) -> None:
        self._config.set_secret("youtube_api_key", self.api_edit.text().strip())
        QMessageBox.information(self, "Saved", "API key saved.")

    def _format_key(self) -> str:
        return FORMATS[self.format_combo.currentIndex()][1]

    # ------------------------------------------------------------------ fetch
    def _fetch(self) -> None:
        channel = self.channel_edit.text().strip()
        if not channel:
            QMessageBox.warning(self, "No channel", "Please enter a channel.")
            return
        self._config.set_setting("youtube_last_channel", channel)
        self.fetch_btn.setEnabled(False)
        self._fetcher.run(
            api_key=self.api_edit.text().strip(),
            channel=channel,
        )

    def _on_data(self, data: Dict[str, Any]) -> None:
        self.fetch_btn.setEnabled(True)
        self._current = data
        self._set_status(
            f"{data.get('title', 'Channel')}: "
            f"{data.get('subscriber_count', 0):,} subs · "
            f"{data.get('view_count', 0):,} views"
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
            QMessageBox.warning(self, "No data", "Fetch the channel first.")
            return
        text = format_youtube_display(self._current, self._format_key())
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
        self._config.set_setting("youtube_use_sprite_font", self.font_picker.use_sprite)
        self._config.set_setting("youtube_sprite_font_name", self.font_picker.font_name)

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
            QMessageBox.warning(self, "No data", "Fetch a channel first.")
            return
        default = f"YouTube - {self._current.get('title', 'Channel')[:15]}"
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=default)
        if not ok or not name.strip():
            return
        preset = {
            "name": name.strip(),
            "type": self.feature_id,
            "channel": self.channel_edit.text().strip(),
            "format": self._format_key(),
            "text_color": self.text_color.color,
            "bg_color": self.bg_color.color,
            "auto_refresh": self.refresh_check.isChecked(),
            "refresh_interval": self.refresh_interval.value(),
        }
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        self.channel_edit.setText(preset.get("channel", "@MrBeast"))
        fmt = preset.get("format", "subscribers")
        for i, (_, key) in enumerate(FORMATS):
            if key == fmt:
                self.format_combo.setCurrentIndex(i)
                break
        self.text_color.set_color(preset.get("text_color", "#FFFFFF"))
        self.bg_color.set_color(preset.get("bg_color", "#000000"))
        self.refresh_check.setChecked(bool(preset.get("auto_refresh", False)))
        self.refresh_interval.setValue(int(preset.get("refresh_interval", 300)))

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
