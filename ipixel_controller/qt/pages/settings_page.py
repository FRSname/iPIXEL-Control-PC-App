"""Settings page — brightness, power, auto-connect, sprite-font library.

The sprite-font library editor lets the user add/update/delete entries
in ``ipixel_settings.json`` → ``sprite_fonts``. Changes are pushed up via
``on_fonts_changed`` so other pages can refresh their pickers.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...services.sprite_font import SpriteFontService
from ..device_bridge import DeviceBridge
from ..widgets import Card
from .base import Page


DEFAULT_TEXT_ORDER = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$% "


class SettingsPage(Page):
    title = "Settings"
    subtitle = "Panel hardware, app preferences, sprite-font library."

    def __init__(
        self,
        device: DeviceBridge,
        config,
        fonts: SpriteFontService,
        on_fonts_changed: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._fonts = fonts
        self._on_fonts_changed = on_fonts_changed

        # ---- Brightness ----
        bright_card = Card(title="Brightness")
        bright_row = QHBoxLayout()
        self.brightness = QSlider(Qt.Horizontal)
        self.brightness.setMinimum(1)
        self.brightness.setMaximum(100)
        self.brightness.setValue(int(config.get_setting("last_brightness", 50)))
        self.brightness_label = QLabel(f"{self.brightness.value()}%")
        self.brightness.valueChanged.connect(
            lambda v: self.brightness_label.setText(f"{v}%")
        )
        apply_brightness = QPushButton("Apply")
        apply_brightness.setObjectName("PrimaryButton")
        apply_brightness.clicked.connect(self._apply_brightness)
        bright_row.addWidget(self.brightness, 1)
        bright_row.addWidget(self.brightness_label)
        bright_row.addWidget(apply_brightness)
        bright_card.add_layout(bright_row)
        self.content_layout().addWidget(bright_card)

        # ---- Power ----
        power_card = Card(title="Power")
        power_row = QHBoxLayout()
        self.power_on_btn = QPushButton("Power on")
        self.power_on_btn.setObjectName("PrimaryButton")
        self.power_on_btn.clicked.connect(lambda: self._device.set_power(True))
        self.power_off_btn = QPushButton("Power off")
        self.power_off_btn.clicked.connect(lambda: self._device.set_power(False))
        power_row.addWidget(self.power_on_btn)
        power_row.addWidget(self.power_off_btn)
        power_row.addStretch()
        power_card.add_layout(power_row)
        self.content_layout().addWidget(power_card)

        # ---- Auto behaviour ----
        auto_card = Card(title="Startup")
        self.auto_connect = QCheckBox("Auto-connect to last device on launch")
        self.auto_connect.setChecked(bool(config.get_setting("auto_connect", True)))
        self.auto_connect.stateChanged.connect(self._save_auto)
        auto_card.add(self.auto_connect)

        self.restore_state = QCheckBox("Restore last preset on launch")
        self.restore_state.setChecked(bool(config.get_setting("restore_last_state", True)))
        self.restore_state.stateChanged.connect(self._save_auto)
        auto_card.add(self.restore_state)
        self.content_layout().addWidget(auto_card)

        # ---- Sprite font library ----
        self.content_layout().addWidget(self._build_sprite_card())

        self.on_connection_changed(self._device.is_connected)

    # ============================================================ brightness
    def _apply_brightness(self) -> None:
        value = self.brightness.value()
        self._device.set_brightness(value)
        self._config.set_setting("last_brightness", value)

    def _save_auto(self) -> None:
        self._config.set_setting("auto_connect", self.auto_connect.isChecked())
        self._config.set_setting("restore_last_state", self.restore_state.isChecked())

    # =========================================================== sprite UI
    def _build_sprite_card(self) -> Card:
        card = Card(title="Sprite-font library")

        body = QHBoxLayout()
        body.setSpacing(14)

        # List of fonts
        self.font_list = QListWidget()
        self.font_list.setMinimumWidth(220)
        self.font_list.currentRowChanged.connect(self._on_font_selected)
        body.addWidget(self.font_list)

        # Form
        form_holder = QWidget()
        form = QFormLayout(form_holder)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.font_name_edit = QLineEdit()
        form.addRow("Name", self.font_name_edit)

        path_row = QHBoxLayout()
        self.font_path_edit = QLineEdit()
        path_row.addWidget(self.font_path_edit, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_sprite_file)
        path_row.addWidget(browse)
        form.addRow("Sprite sheet", path_row)

        self.font_order_edit = QLineEdit(DEFAULT_TEXT_ORDER)
        form.addRow("Glyph order", self.font_order_edit)

        self.font_cols_spin = QSpinBox()
        self.font_cols_spin.setRange(1, 256)
        self.font_cols_spin.setValue(73)
        form.addRow("Columns", self.font_cols_spin)

        action_row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_font)
        update_btn = QPushButton("Update")
        update_btn.clicked.connect(self._update_font)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_font)
        clear_btn = QPushButton("Clear form")
        clear_btn.clicked.connect(self._clear_form)
        action_row.addWidget(add_btn)
        action_row.addWidget(update_btn)
        action_row.addWidget(delete_btn)
        action_row.addWidget(clear_btn)
        action_row.addStretch()
        form.addRow("", self._wrap_layout(action_row))

        body.addWidget(form_holder, 1)
        card.add_layout(body)

        self._refresh_font_list()
        return card

    @staticmethod
    def _wrap_layout(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _refresh_font_list(self) -> None:
        self.font_list.blockSignals(True)
        self.font_list.clear()
        for f in self._config.get_sprite_fonts():
            self.font_list.addItem(f.get("name", "Unnamed"))
        self.font_list.blockSignals(False)

    def _on_font_selected(self, row: int) -> None:
        fonts = self._config.get_sprite_fonts()
        if 0 <= row < len(fonts):
            f = fonts[row]
            self.font_name_edit.setText(f.get("name", ""))
            self.font_path_edit.setText(f.get("path", ""))
            self.font_order_edit.setText(f.get("order", DEFAULT_TEXT_ORDER))
            self.font_cols_spin.setValue(int(f.get("cols", 1)))

    def _browse_sprite_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sprite sheet",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*.*)",
        )
        if path:
            self.font_path_edit.setText(path)

    def _form_values(self) -> Optional[dict]:
        name = self.font_name_edit.text().strip()
        path = self.font_path_edit.text().strip()
        order = self.font_order_edit.text()
        cols = self.font_cols_spin.value()
        if not name:
            QMessageBox.warning(self, "No name", "Enter a font name.")
            return None
        if not path:
            QMessageBox.warning(self, "No path", "Select a sprite sheet.")
            return None
        return {"name": name, "path": path, "order": order, "cols": cols}

    def _add_font(self) -> None:
        font = self._form_values()
        if font is None:
            return
        self._config.add_sprite_font(font)
        self._refresh_font_list()
        self._notify_fonts_changed()
        self._clear_form()

    def _update_font(self) -> None:
        row = self.font_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No selection", "Select a font to update.")
            return
        font = self._form_values()
        if font is None:
            return
        self._config.update_sprite_font(row, font)
        self._refresh_font_list()
        self.font_list.setCurrentRow(row)
        self._notify_fonts_changed()

    def _delete_font(self) -> None:
        row = self.font_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No selection", "Select a font to delete.")
            return
        if QMessageBox.question(self, "Confirm", "Delete this sprite font?") \
                != QMessageBox.Yes:
            return
        self._config.remove_sprite_font(row)
        self._refresh_font_list()
        self._notify_fonts_changed()
        self._clear_form()

    def _clear_form(self) -> None:
        self.font_name_edit.clear()
        self.font_path_edit.clear()
        self.font_order_edit.setText(DEFAULT_TEXT_ORDER)
        self.font_cols_spin.setValue(73)

    def _notify_fonts_changed(self) -> None:
        if self._on_fonts_changed is not None:
            self._on_fonts_changed()

    # =========================================================== connection
    def on_connection_changed(self, connected: bool) -> None:
        for w in (self.power_on_btn, self.power_off_btn):
            w.setEnabled(connected)
