"""Clock feature, ported to PySide6.

Three modes:
- **Built-in** — uses the panel's native clock styles 0–8 (low-update, no
  live timer needed).
- **Custom** — sends a formatted time string on a QTimer.
- **Countdown** — counts down to a target ``QDateTime`` on a 1 s tick.

Sprite-font rendering is intentionally left for a follow-up — once the
Qt sprite-font picker exists it can be plugged in here.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...services.sprite_font import SpriteFontService
from ..device_bridge import DeviceBridge
from ..sprite_sender import SpriteSender
from ..widgets import Card, ColorButton, SpriteFontPicker
from .base import Page


TIME_FORMATS = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%H.%M"]
COUNTDOWN_FORMATS = [
    ("Days Hours Mins", "days_hours_mins"),
    ("Hours Mins Secs", "hours_mins_secs"),
    ("Days Only", "days_only"),
    ("Full", "full"),
]

MODE_BUILTIN = "built-in"
MODE_CUSTOM = "custom"
MODE_COUNTDOWN = "countdown"


class ClockPage(Page):
    title = "Clock"
    subtitle = "Built-in panel clock, live custom format, or a countdown."
    feature_id = "clock"

    def __init__(self, device: DeviceBridge, config, fonts: SpriteFontService) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._fonts = fonts
        self._sender = SpriteSender(device, fonts, temp_basename="ipixel_clock.png")
        self._mode = MODE_BUILTIN

        # Live-update timer drives custom + countdown modes.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # ------------------------------------------------------- mode picker
        # Build the radios but do NOT connect toggled / set checked yet — the
        # mode-specific subviews live in self._stack which is constructed
        # below, and _on_mode_toggled assumes it already exists.
        mode_card = Card(title="Mode")
        mode_row = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._mode_radios = []
        for key, label in (
            (MODE_BUILTIN, "Built-in"),
            (MODE_CUSTOM, "Custom"),
            (MODE_COUNTDOWN, "Countdown"),
        ):
            rb = QRadioButton(label)
            rb.setProperty("mode", key)
            self._mode_group.addButton(rb)
            mode_row.addWidget(rb)
            self._mode_radios.append(rb)
        mode_row.addStretch()
        mode_card.add_layout(mode_row)
        self.content_layout().addWidget(mode_card)

        # ----------------------------------------------------- mode-specific
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_builtin())
        self._stack.addWidget(self._build_custom())
        self._stack.addWidget(self._build_countdown())
        self.content_layout().addWidget(self._stack)

        # Now safe to wire the signal and select the initial mode.
        for rb in self._mode_radios:
            rb.toggled.connect(self._on_mode_toggled)
        self._mode_radios[0].setChecked(True)

        # --------------------------------------------------------- action row
        row = QHBoxLayout()
        self.show_btn = QPushButton("Show clock")
        self.show_btn.setObjectName("PrimaryButton")
        self.show_btn.clicked.connect(self._show)
        row.addWidget(self.show_btn)

        self.live_btn = QPushButton("Start live")
        self.live_btn.clicked.connect(self._toggle_live)
        row.addWidget(self.live_btn)

        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self._stop_live)
        row.addWidget(stop_btn)

        save_btn = QPushButton("Save as preset")
        save_btn.clicked.connect(self._save_preset)
        row.addWidget(save_btn)
        row.addStretch()
        self.content_layout().addLayout(row)

        self.on_connection_changed(self._device.is_connected)

    # ------------------------------------------------------------- sub-views
    def _build_builtin(self) -> QWidget:
        card = Card(title="Built-in clock")
        grid = QGridLayout()
        grid.setSpacing(8)
        self._style_group = QButtonGroup(self)
        self._style_radios = []
        for i in range(9):
            rb = QRadioButton(f"Style {i}")
            rb.setProperty("style", i)
            self._style_group.addButton(rb)
            self._style_radios.append(rb)
            grid.addWidget(rb, i // 3, i % 3)
            if i == 0:
                rb.setChecked(True)
        card.add_layout(grid)
        return card

    def _build_custom(self) -> QWidget:
        card = Card(title="Custom clock")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.format_combo = QComboBox()
        for f in TIME_FORMATS:
            self.format_combo.addItem(f)
        form.addRow("Format", self.format_combo)

        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("Text"))
        self.custom_text_color = ColorButton("#FFFFFF")
        col_row.addWidget(self.custom_text_color)
        col_row.addSpacing(16)
        col_row.addWidget(QLabel("Background"))
        self.custom_bg_color = ColorButton("#000000")
        col_row.addWidget(self.custom_bg_color)
        col_row.addStretch()
        form.addRow("Colours", col_row)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(1)
        self.interval_spin.setSuffix(" s")
        form.addRow("Update every", self.interval_spin)

        # Sprite font picker (shared across Custom + Countdown modes)
        names = self._config.get_sprite_font_names()
        self.font_picker = SpriteFontPicker(
            font_names=names,
            use_sprite=bool(self._config.get_setting("clock_use_time_sprite", False)),
            font_name=self._config.get_setting(
                "clock_time_sprite_font_name", names[0] if names else ""
            ),
        )
        self.font_picker.changed.connect(self._on_font_change)
        form.addRow("Sprite font", self.font_picker)

        card.add_layout(form)
        return card

    def _build_countdown(self) -> QWidget:
        card = Card(title="Countdown")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.event_edit = QLineEdit("Event")
        form.addRow("Event", self.event_edit)

        self.target_edit = QDateTimeEdit(QDateTime.currentDateTime().addDays(1))
        self.target_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.target_edit.setCalendarPopup(True)
        form.addRow("Target", self.target_edit)

        self.countdown_format = QComboBox()
        for label, _ in COUNTDOWN_FORMATS:
            self.countdown_format.addItem(label)
        form.addRow("Display", self.countdown_format)

        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("Text"))
        self.count_text_color = ColorButton("#00FF00")
        col_row.addWidget(self.count_text_color)
        col_row.addSpacing(16)
        col_row.addWidget(QLabel("Background"))
        self.count_bg_color = ColorButton("#000000")
        col_row.addWidget(self.count_bg_color)
        col_row.addStretch()
        form.addRow("Colours", col_row)

        card.add_layout(form)
        return card

    # -------------------------------------------------------------- behaviour
    def _on_mode_toggled(self, checked: bool) -> None:
        if not checked:
            return
        for btn in self._mode_group.buttons():
            if btn.isChecked():
                self._mode = btn.property("mode")
                break
        index = {MODE_BUILTIN: 0, MODE_CUSTOM: 1, MODE_COUNTDOWN: 2}[self._mode]
        self._stack.setCurrentIndex(index)
        # Switching mode stops any live updates from the previous mode
        self._stop_live(silent=True)

    def _selected_style(self) -> int:
        for rb in self._style_radios:
            if rb.isChecked():
                return int(rb.property("style"))
        return 0

    def _countdown_format_key(self) -> str:
        return COUNTDOWN_FORMATS[self.countdown_format.currentIndex()][1]

    def _send_time_text(self, text: str, color: str, bg: str) -> None:
        if self.font_picker.use_sprite and self.font_picker.font_name:
            self._sender.send_static(text, self.font_picker.font_name, bg)
            return
        self._device.send_text(
            text,
            char_height=16,
            color=color,
            bg_color=bg,
            animation=0,
            speed=50,
        )

    def _on_font_change(self) -> None:
        self._config.set_setting("clock_use_time_sprite", self.font_picker.use_sprite)
        self._config.set_setting(
            "clock_time_sprite_font_name", self.font_picker.font_name
        )

    def refresh_font_list(self, names) -> None:
        self.font_picker.set_fonts(names)

    # ---------------------------------------------------------------- show
    def _show(self) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return
        if self._mode == MODE_BUILTIN:
            self._device.set_clock_mode(style=self._selected_style())
        elif self._mode == MODE_CUSTOM:
            self._send_custom_once()
        else:
            self._send_countdown_once()

    def _send_custom_once(self) -> None:
        fmt = self.format_combo.currentText()
        self._send_time_text(
            datetime.now().strftime(fmt),
            self.custom_text_color.color,
            self.custom_bg_color.color,
        )

    def _send_countdown_once(self) -> None:
        target_qdt = self.target_edit.dateTime()
        target = target_qdt.toPython()
        remaining = target - datetime.now()
        if remaining.total_seconds() <= 0:
            text = "NOW!"
        else:
            text = self._format_remaining(remaining)
        self._send_time_text(
            text, self.count_text_color.color, self.count_bg_color.color
        )

    def _format_remaining(self, delta: timedelta) -> str:
        total = int(delta.total_seconds())
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        fmt = self._countdown_format_key()
        if fmt == "days_hours_mins":
            return f"{days}d {hours}h {mins}m"
        if fmt == "hours_mins_secs":
            return f"{hours}:{mins:02d}:{secs:02d}"
        if fmt == "days_only":
            return f"{days} days"
        return f"{days}d {hours}:{mins:02d}:{secs:02d}"

    # ---------------------------------------------------------------- live
    def _toggle_live(self) -> None:
        if self._timer.isActive():
            self._stop_live()
        else:
            self._start_live()

    def _start_live(self) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return
        if self._mode == MODE_BUILTIN:
            # Built-in clock self-updates on the panel; no live loop needed.
            self._show()
            return
        interval_ms = (
            self.interval_spin.value() * 1000 if self._mode == MODE_CUSTOM else 1000
        )
        self._tick()  # send immediately
        self._timer.start(interval_ms)
        self.live_btn.setText("Stop live")

    def _stop_live(self, silent: bool = False) -> None:
        if self._timer.isActive():
            self._timer.stop()
        self._sender.stop()
        self.live_btn.setText("Start live")

    def _tick(self) -> None:
        if self._mode == MODE_CUSTOM:
            self._send_custom_once()
        elif self._mode == MODE_COUNTDOWN:
            self._send_countdown_once()

    # --------------------------------------------------------------- preset
    def _save_preset(self) -> None:
        default = f"Clock - {self._mode}"
        if self._mode == MODE_COUNTDOWN:
            default = f"Countdown - {self.event_edit.text() or 'Event'}"
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=default)
        if not ok or not name.strip():
            return

        preset: Dict[str, Any] = {
            "name": name.strip(),
            "type": self.feature_id,
            "clock_mode": self._mode,
        }
        if self._mode == MODE_BUILTIN:
            preset["clock_style"] = self._selected_style()
        elif self._mode == MODE_CUSTOM:
            preset.update(
                {
                    "time_format": self.format_combo.currentText(),
                    "clock_color": self.custom_text_color.color,
                    "clock_bg_color": self.custom_bg_color.color,
                    "clock_update_interval": self.interval_spin.value(),
                }
            )
        else:  # countdown
            t = self.target_edit.dateTime()
            preset.update(
                {
                    "countdown_event": self.event_edit.text(),
                    "countdown_year": t.date().year(),
                    "countdown_month": t.date().month(),
                    "countdown_day": t.date().day(),
                    "countdown_hour": t.time().hour(),
                    "countdown_minute": t.time().minute(),
                    "countdown_format": self._countdown_format_key(),
                    "countdown_color": self.count_text_color.color,
                    "countdown_bg_color": self.count_bg_color.color,
                }
            )
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        mode = preset.get("clock_mode", MODE_BUILTIN)
        for btn in self._mode_group.buttons():
            if btn.property("mode") == mode:
                btn.setChecked(True)
                break
        if mode == MODE_BUILTIN:
            style = int(preset.get("clock_style", 0))
            self._style_radios[max(0, min(8, style))].setChecked(True)
            self._show()
        elif mode == MODE_CUSTOM:
            self.format_combo.setCurrentText(preset.get("time_format", "%H:%M"))
            self.custom_text_color.set_color(preset.get("clock_color", "#FFFFFF"))
            self.custom_bg_color.set_color(preset.get("clock_bg_color", "#000000"))
            self.interval_spin.setValue(int(preset.get("clock_update_interval", 1)))
            self._start_live()
        else:
            target = QDateTime(
                int(preset.get("countdown_year", 2026)),
                int(preset.get("countdown_month", 1)),
                int(preset.get("countdown_day", 1)),
                int(preset.get("countdown_hour", 0)),
                int(preset.get("countdown_minute", 0)),
            )
            self.target_edit.setDateTime(target)
            self.event_edit.setText(preset.get("countdown_event", ""))
            fmt_key = preset.get("countdown_format", "days_hours_mins")
            for i, (_, key) in enumerate(COUNTDOWN_FORMATS):
                if key == fmt_key:
                    self.countdown_format.setCurrentIndex(i)
                    break
            self.count_text_color.set_color(preset.get("countdown_color", "#00FF00"))
            self.count_bg_color.set_color(preset.get("countdown_bg_color", "#000000"))
            self._start_live()
        return True

    # ----------------------------------------------------------------- state
    def on_connection_changed(self, connected: bool) -> None:
        self.show_btn.setEnabled(connected)
        self.live_btn.setEnabled(connected)
        if not connected:
            self._stop_live(silent=True)
