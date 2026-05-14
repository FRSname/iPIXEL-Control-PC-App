"""Procedural animation feature, ported to PySide6.

Reuses the framework-agnostic
:class:`ipixel_controller.services.animation_generator.AnimationGenerator`
to render frames; sends each frame to the panel as a temp image. Frame
pacing runs on a QTimer rather than the legacy Tk timer manager.
"""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QWidget,
)

from ...services.animation_generator import (
    AnimationGenerator,
    AnimationState,
    AnimationType,
    ColorScheme,
)
from ...utils.image_utils import save_temp_image
from ..device_bridge import DeviceBridge
from ..widgets import Card
from .base import Page


ANIMATIONS = [
    ("Game of Life", AnimationType.GAME_OF_LIFE),
    ("Matrix rain", AnimationType.MATRIX_RAIN),
    ("Fire", AnimationType.FIRE),
    ("Starfield", AnimationType.STARFIELD),
    ("Plasma", AnimationType.PLASMA),
]

COLOR_SCHEMES = [
    ("White", ColorScheme.WHITE),
    ("Green", ColorScheme.GREEN),
    ("Blue", ColorScheme.BLUE),
    ("Red", ColorScheme.RED),
    ("Rainbow", ColorScheme.RAINBOW),
]


class AnimationPage(Page):
    title = "Animations"
    subtitle = "Procedural pixel-art animations rendered on the fly. No API key needed."
    feature_id = "animation"

    def __init__(self, device: DeviceBridge, config) -> None:
        super().__init__()
        self._device = device
        self._config = config

        self._generator = AnimationGenerator(64, 16)
        self._anim_state = AnimationState()
        self._frame = 0
        self._total_frames: float = float("inf")
        self._running = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

        # ----- Type
        type_card = Card(title="Type")
        grid = QGridLayout()
        grid.setSpacing(8)
        self._type_group = QButtonGroup(self)
        self._type_radios = []
        for i, (label, value) in enumerate(ANIMATIONS):
            rb = QRadioButton(label)
            rb.setProperty("value", value)
            self._type_group.addButton(rb)
            self._type_radios.append(rb)
            grid.addWidget(rb, i // 3, i % 3)
            if i == 0:
                rb.setChecked(True)
        self._type_group.buttonToggled.connect(self._on_type_change)
        type_card.add_layout(grid)
        self.content_layout().addWidget(type_card)

        # ----- Options
        opts = Card(title="Options")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.color_combo = QComboBox()
        for label, _ in COLOR_SCHEMES:
            self.color_combo.addItem(label)
        self.color_combo.setCurrentIndex(1)  # green
        form.addRow("Colour scheme", self.color_combo)

        fps_row = QHBoxLayout()
        self.fps_slider = QSlider(Qt.Horizontal)
        self.fps_slider.setMinimum(1)
        self.fps_slider.setMaximum(30)
        self.fps_slider.setValue(10)
        self.fps_label = QLabel("10 fps")
        self.fps_slider.valueChanged.connect(
            lambda v: self.fps_label.setText(f"{v} fps")
        )
        fps_row.addWidget(self.fps_slider, 1)
        fps_row.addWidget(self.fps_label)
        form.addRow("Speed", fps_row)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 600)
        self.duration_spin.setValue(0)
        self.duration_spin.setSuffix(" s (0 = infinite)")
        form.addRow("Duration", self.duration_spin)

        # GoL-only option
        density_row = QHBoxLayout()
        self.density_slider = QSlider(Qt.Horizontal)
        self.density_slider.setMinimum(10)
        self.density_slider.setMaximum(50)
        self.density_slider.setValue(30)
        self.density_label = QLabel("0.30")
        self.density_slider.valueChanged.connect(
            lambda v: self.density_label.setText(f"{v/100:.2f}")
        )
        density_row.addWidget(self.density_slider, 1)
        density_row.addWidget(self.density_label)
        self.density_widget = QWidget()
        density_layout = QHBoxLayout(self.density_widget)
        density_layout.setContentsMargins(0, 0, 0, 0)
        density_layout.addLayout(density_row)
        self._density_row_label = QLabel("Initial density")
        form.addRow(self._density_row_label, self.density_widget)

        opts.add_layout(form)
        self.content_layout().addWidget(opts)

        # ----- Status + actions
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color:#a6adc8;")
        self.content_layout().addWidget(self.status_label)

        row = QHBoxLayout()
        self.start_btn = QPushButton("Start animation")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self._start)
        row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        row.addWidget(self.stop_btn)

        save_btn = QPushButton("Save as preset")
        save_btn.clicked.connect(self._save_preset)
        row.addWidget(save_btn)
        row.addStretch()
        self.content_layout().addLayout(row)

        # Initial visibility
        self._refresh_density_visibility()
        self.on_connection_changed(self._device.is_connected)

    # ---------------------------------------------------------------- helpers
    def _selected_type(self) -> str:
        for rb in self._type_radios:
            if rb.isChecked():
                return rb.property("value")
        return AnimationType.GAME_OF_LIFE

    def _selected_color(self) -> str:
        return COLOR_SCHEMES[self.color_combo.currentIndex()][1]

    def _on_type_change(self, *_args) -> None:
        self._refresh_density_visibility()

    def _refresh_density_visibility(self) -> None:
        is_gol = self._selected_type() == AnimationType.GAME_OF_LIFE
        self.density_widget.setVisible(is_gol)
        self._density_row_label.setVisible(is_gol)

    # ------------------------------------------------------------------ run
    def _start(self) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return
        self._anim_state = AnimationState()
        self._frame = 0
        duration = self.duration_spin.value()
        fps = self.fps_slider.value()
        self._total_frames = duration * fps if duration > 0 else float("inf")
        self._running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running…")
        self._timer.start(max(1, 1000 // fps))

    def _stop(self) -> None:
        self._running = False
        self._timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopped")

    def _next_frame(self) -> None:
        if not self._running:
            return
        if self._frame >= self._total_frames:
            self._stop()
            return

        anim_type = self._selected_type()
        options: Dict[str, Any] = {}
        if anim_type == AnimationType.GAME_OF_LIFE:
            options["density"] = self.density_slider.value() / 100

        img = self._generator.generate_frame(
            anim_type,
            self._frame,
            self._selected_color(),
            self._anim_state,
            **options,
        )

        path = save_temp_image(img, "ipixel_anim.png")
        self._device.send_image(path, resize_method="crop", save_slot=0)

        self._frame += 1
        if self._total_frames != float("inf"):
            remaining = int(
                (self._total_frames - self._frame) / max(1, self.fps_slider.value())
            )
            self.status_label.setText(
                f"Frame {self._frame}/{int(self._total_frames)} · {remaining}s left"
            )
        else:
            self.status_label.setText(f"Frame {self._frame}")

    # --------------------------------------------------------------- preset
    def _save_preset(self) -> None:
        type_name = next((n for n, v in ANIMATIONS if v == self._selected_type()), "Animation")
        name, ok = QInputDialog.getText(
            self, "Save preset", "Preset name:", text=f"Animation - {type_name}"
        )
        if not ok or not name.strip():
            return
        preset = {
            "name": name.strip(),
            "type": self.feature_id,
            "anim_type": self._selected_type(),
            "color_scheme": self._selected_color(),
            "fps": self.fps_slider.value(),
            "duration": self.duration_spin.value(),
            "density": self.density_slider.value() / 100,
        }
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        anim_type = preset.get("anim_type", AnimationType.GAME_OF_LIFE)
        for rb in self._type_radios:
            if rb.property("value") == anim_type:
                rb.setChecked(True)
                break
        color = preset.get("color_scheme", ColorScheme.GREEN)
        for i, (_, value) in enumerate(COLOR_SCHEMES):
            if value == color:
                self.color_combo.setCurrentIndex(i)
                break
        self.fps_slider.setValue(int(preset.get("fps", 10)))
        self.duration_spin.setValue(int(preset.get("duration", 0)))
        self.density_slider.setValue(int(float(preset.get("density", 0.3)) * 100))
        self._refresh_density_visibility()
        self._start()
        return True

    # ----------------------------------------------------------------- state
    def on_connection_changed(self, connected: bool) -> None:
        self.start_btn.setEnabled(connected and not self._running)
        if not connected and self._running:
            self._stop()
