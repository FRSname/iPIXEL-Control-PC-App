"""Text feature, ported to PySide6.

Two rendering paths:

- **Built-in panel text** — fast, uses `device.send_text`. Background
  colour rendering is firmware-limited on some panels (whites look dim).
- **Sprite font** — renders the text into a PIL image with the chosen
  sprite sheet and sends it via `device.send_image`. Bright/coloured
  backgrounds work correctly here because the background is just part of
  the image.

The animation effect drives the sprite-font path too: Static centres the
text on a 64×16 canvas, Scroll Left/Right runs a smooth scroll, Blink
falls back to the built-in send (firmware drives the blink directly).
"""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from ...services.sprite_font import SpriteFontService
from ..device_bridge import DeviceBridge
from ..sprite_sender import SpriteSender
from ..widgets import Card, ColorButton, SpriteFontPicker
from .base import Page


ANIMATIONS = [
    ("Static", 0),
    ("Scroll left", 1),
    ("Scroll right", 2),
    ("Blink", 5),
]


class TextPage(Page):
    title = "Text"
    subtitle = "Send a message to the panel. Sprite fonts give you full background-colour control."
    feature_id = "text"

    def __init__(
        self,
        device: DeviceBridge,
        config,
        fonts: SpriteFontService,
    ) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._fonts = fonts
        self._sender = SpriteSender(device, fonts, temp_basename="ipixel_text.png")

        # --- Message ---
        msg_card = Card(title="Message")
        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText("Hello World")
        self.text_input.setPlainText("Hello World")
        self.text_input.setFixedHeight(80)
        msg_card.add(self.text_input)
        self.content_layout().addWidget(msg_card)

        # --- Colours ---
        color_card = Card(title="Colours")
        color_row = QHBoxLayout()
        color_row.setSpacing(20)
        color_row.addWidget(QLabel("Text"))
        self.text_color_btn = ColorButton("#FFFFFF")
        color_row.addWidget(self.text_color_btn)
        color_row.addSpacing(20)
        color_row.addWidget(QLabel("Background"))
        self.bg_color_btn = ColorButton("#000000")
        color_row.addWidget(self.bg_color_btn)
        color_row.addStretch()
        color_card.add_layout(color_row)
        self.rainbow_check = QCheckBox(
            "Rainbow mode (built-in path only — overrides text colour)"
        )
        color_card.add(self.rainbow_check)
        self.content_layout().addWidget(color_card)

        # --- Sprite font ---
        font_card = Card(title="Sprite font")
        names = self._config.get_sprite_font_names()
        self.font_picker = SpriteFontPicker(
            font_names=names,
            use_sprite=bool(self._config.get_setting("text_use_sprite_font", False)),
            font_name=self._config.get_setting("text_sprite_font_name", names[0] if names else ""),
        )
        self.font_picker.changed.connect(self._on_font_change)
        font_card.add(self.font_picker)
        hint = QLabel(
            "When on, text is rendered as an image — background colours "
            "(including white) display correctly."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#6c7086;")
        font_card.add(hint)
        self.content_layout().addWidget(font_card)

        # --- Animation ---
        anim_card = Card(title="Animation")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.anim_combo = QComboBox()
        for label, _ in ANIMATIONS:
            self.anim_combo.addItem(label)
        form.addRow("Effect", self.anim_combo)

        speed_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(100)
        self.speed_slider.setValue(50)
        self.speed_value = QLabel("50")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_value.setText(str(v))
        )
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_value)
        form.addRow("Speed", speed_row)
        anim_card.add_layout(form)
        self.content_layout().addWidget(anim_card)

        # --- Actions ---
        action_row = QHBoxLayout()
        self.send_btn = QPushButton("Send to panel")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._send)
        action_row.addWidget(self.send_btn)

        self.save_btn = QPushButton("Save as preset")
        self.save_btn.clicked.connect(self._save_preset)
        action_row.addWidget(self.save_btn)
        action_row.addStretch()
        self.content_layout().addLayout(action_row)

        self.on_connection_changed(self._device.is_connected)

    # ----------------------------------------------------------- preferences
    def _on_font_change(self) -> None:
        self._config.set_setting("text_use_sprite_font", self.font_picker.use_sprite)
        self._config.set_setting("text_sprite_font_name", self.font_picker.font_name)

    def refresh_font_list(self, names: List[str]) -> None:
        """Called by MainWindow when the sprite-font library changes."""
        self.font_picker.set_fonts(names)

    # ------------------------------------------------------------- connection
    def on_connection_changed(self, connected: bool) -> None:
        self.send_btn.setEnabled(connected)
        if not connected:
            self._sender.stop()

    # ------------------------------------------------------------------ send
    def _gather(self) -> Dict[str, Any]:
        return {
            "text": self.text_input.toPlainText().strip(),
            "text_color": self.text_color_btn.color,
            "bg_color": self.bg_color_btn.color,
            "animation": ANIMATIONS[self.anim_combo.currentIndex()][1],
            "speed": self.speed_slider.value(),
            "rainbow": 1 if self.rainbow_check.isChecked() else 0,
            "use_sprite": self.font_picker.use_sprite,
            "font_name": self.font_picker.font_name,
        }

    def _send(self) -> None:
        p = self._gather()
        if not p["text"]:
            QMessageBox.warning(self, "No text", "Please enter some text.")
            return
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return

        # Cancel any in-flight scroll from a previous send.
        self._sender.stop()

        if p["use_sprite"] and p["font_name"]:
            err = self._send_via_sprite(p)
            if err:
                QMessageBox.critical(self, "Sprite font error", err)
            return

        # Fallback: built-in panel text rendering.
        self._device.send_text(
            p["text"],
            char_height=16,
            color=p["text_color"],
            bg_color=p["bg_color"],
            animation=p["animation"],
            speed=101 - p["speed"],
            rainbow_mode=p["rainbow"],
        )

    def _send_via_sprite(self, p: Dict[str, Any]) -> str | None:
        anim = p["animation"]
        if anim == 1 or anim == 2:  # scroll left / right
            return self._sender.start_scroll(
                p["text"],
                font_name=p["font_name"],
                bg_color=p["bg_color"],
                speed=p["speed"],
                reverse=(anim == 2),
            )
        # Static (0) and Blink (5) fall back to a single static render.
        # Blink animation in firmware isn't reachable from the image path;
        # users wanting blink should keep sprite mode off.
        return self._sender.send_static(p["text"], p["font_name"], p["bg_color"])

    # ---------------------------------------------------------------- preset
    def _save_preset(self) -> None:
        p = self._gather()
        if not p["text"]:
            QMessageBox.warning(self, "No text", "Please enter some text.")
            return
        name, ok = QInputDialog.getText(
            self, "Save preset", "Preset name:", text=p["text"][:20]
        )
        if not ok or not name.strip():
            return
        preset = {
            "name": name.strip(),
            "type": self.feature_id,
            **{k: v for k, v in p.items() if k not in ("use_sprite", "font_name")},
            "text_use_sprite_font": p["use_sprite"],
            "text_sprite_font_name": p["font_name"],
        }
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        self.text_input.setPlainText(preset.get("text", ""))
        self.text_color_btn.set_color(preset.get("text_color", "#FFFFFF"))
        self.bg_color_btn.set_color(preset.get("bg_color", "#000000"))
        anim_value = preset.get("animation", 0)
        for i, (_, v) in enumerate(ANIMATIONS):
            if v == anim_value:
                self.anim_combo.setCurrentIndex(i)
                break
        self.speed_slider.setValue(int(preset.get("speed", 50)))
        self.rainbow_check.setChecked(bool(preset.get("rainbow", 0)))
        self.font_picker.set_use_sprite(bool(preset.get("text_use_sprite_font", False)))
        self.font_picker.set_font_name(preset.get("text_sprite_font_name", ""))
        self._send()
        return True
