"""Image feature, ported to PySide6.

Load an image from disk, preview it, send it to the panel. Presets store
the original path; the thumbnail used by the home tile is generated on
the fly when the preset is created.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...utils.paths import is_valid_image_path, resolve_asset_path
from ..device_bridge import DeviceBridge
from ..widgets import Card
from .base import Page


PREVIEW_W = 384
PREVIEW_H = 96


class ImagePage(Page):
    title = "Image"
    subtitle = "Load a PNG, JPG, GIF or BMP and send it to the panel."
    feature_id = "image"

    def __init__(self, device: DeviceBridge, config) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._image_path: Optional[str] = None

        preview_card = Card(title="Preview")
        self.preview_label = QLabel("No image loaded")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(PREVIEW_H + 24)
        self.preview_label.setStyleSheet(
            "background:#11111b; border:1px solid #45475a; border-radius:6px; "
            "color:#6c7086; padding:12px;"
        )
        preview_card.add(self.preview_label)

        self.path_label = QLabel("No image selected")
        self.path_label.setStyleSheet("color:#a6adc8;")
        preview_card.add(self.path_label)

        self.content_layout().addWidget(preview_card)

        # Actions
        row = QHBoxLayout()
        load_btn = QPushButton("Load image…")
        load_btn.clicked.connect(self._load)
        row.addWidget(load_btn)

        self.send_btn = QPushButton("Send to panel")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)

        save_btn = QPushButton("Save as preset")
        save_btn.clicked.connect(self._save_preset)
        row.addWidget(save_btn)

        row.addStretch()
        self.content_layout().addLayout(row)

        self.on_connection_changed(self._device.is_connected)

    # ---------------------------------------------------------------- helpers
    def _set_image(self, path: str) -> bool:
        resolved = resolve_asset_path(path)
        if not is_valid_image_path(resolved):
            QMessageBox.critical(self, "Invalid image", f"Not a valid image: {path}")
            return False

        self._image_path = path
        self.path_label.setText(os.path.basename(path))

        try:
            img = Image.open(resolved)
            img.thumbnail((PREVIEW_W, PREVIEW_H), Image.NEAREST)
            qimg = ImageQt(img.convert("RGBA"))
            pix = QPixmap.fromImage(qimg)
            self.preview_label.setPixmap(pix)
            self.preview_label.setText("")
        except Exception as e:  # noqa: BLE001
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(f"Preview error: {e}")
        return True

    # ----------------------------------------------------------------- events
    def _load(self) -> None:
        filters = (
            "Images (*.png *.jpg *.jpeg *.gif *.bmp);;"
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;GIF (*.gif);;BMP (*.bmp);;"
            "All files (*.*)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Select image", "", filters)
        if path:
            self._set_image(path)

    def _send(self) -> None:
        if not self._image_path:
            QMessageBox.warning(self, "No image", "Load an image first.")
            return
        resolved = resolve_asset_path(self._image_path)
        if not is_valid_image_path(resolved):
            QMessageBox.critical(self, "Missing", "Image file no longer exists.")
            return
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return
        self._device.send_image(resolved, resize_method="crop", save_slot=0)

    # ----------------------------------------------------------------- preset
    def _save_preset(self) -> None:
        if not self._image_path:
            QMessageBox.warning(self, "No image", "Load an image first.")
            return
        default = os.path.splitext(os.path.basename(self._image_path))[0][:20]
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=default)
        if not ok or not name.strip():
            return
        preset = {
            "name": name.strip(),
            "type": self.feature_id,
            "image_path": self._image_path,
        }
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        path = preset.get("image_path")
        if not path:
            return False
        if not self._set_image(path):
            return False
        self._send()
        return True

    # ------------------------------------------------------------- connection
    def on_connection_changed(self, connected: bool) -> None:
        self.send_btn.setEnabled(connected)
