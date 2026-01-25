"""
Pixel art animation feature.

Generates and displays procedural animations on the LED panel.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from .base import FeatureBase
from ..core.timers import TimerNames
from ..services.animation_generator import (
    AnimationGenerator,
    AnimationState,
    AnimationType,
    ColorScheme,
)


class AnimationFeature(FeatureBase):
    """
    Pixel art animation feature.

    Generates procedural animations:
    - Conway's Game of Life
    - Matrix rain effect
    - Fire simulation
    - Starfield
    - Plasma waves
    """

    feature_id = "animation"
    display_name = "Animations"
    tab_icon = "🎨"

    ANIMATION_TYPES = [
        ("Game of Life", AnimationType.GAME_OF_LIFE),
        ("Matrix Rain", AnimationType.MATRIX_RAIN),
        ("Fire Effect", AnimationType.FIRE),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generator = AnimationGenerator(64, 16)
        self.anim_state = AnimationState()
        self.frame_num = 0

    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """Create the animation tab UI."""
        self.tab_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.tab_frame, text=self.tab_title)

        # Info
        info = self._create_info_label(
            self.tab_frame,
            "Generate procedural pixel art animations.\nNo API key required!"
        )
        info.pack(anchor=tk.W, pady=(0, 10))

        # Animation type
        type_frame = ttk.LabelFrame(self.tab_frame, text="Animation Type", padding="10")
        type_frame.pack(fill=tk.X, pady=(0, 10))

        self.type_var = tk.StringVar(value=AnimationType.GAME_OF_LIFE)
        for i, (name, value) in enumerate(self.ANIMATION_TYPES):
            ttk.Radiobutton(
                type_frame,
                text=name,
                variable=self.type_var,
                value=value,
                command=self._on_type_change
            ).grid(row=i // 3, column=i % 3, sticky=tk.W, padx=(0, 20), pady=2)

        # Options
        options_frame = ttk.LabelFrame(self.tab_frame, text="Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        # Color scheme
        color_row = ttk.Frame(options_frame)
        color_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(color_row, text="Color Scheme:").pack(side=tk.LEFT)
        self.color_var = tk.StringVar(value=ColorScheme.GREEN)
        color_combo = ttk.Combobox(
            color_row,
            values=[c[0] for c in self.COLOR_SCHEMES],
            state="readonly",
            width=15
        )
        color_combo.current(1)  # Green default
        color_combo.pack(side=tk.LEFT, padx=(5, 0))
        color_combo.bind('<<ComboboxSelected>>',
            lambda e: self.color_var.set(self.COLOR_SCHEMES[color_combo.current()][1]))

        # Speed (FPS)
        speed_row = ttk.Frame(options_frame)
        speed_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(speed_row, text="Speed (FPS):").pack(side=tk.LEFT)
        self.fps_var = tk.IntVar(value=10)
        ttk.Scale(
            speed_row,
            from_=1,
            to=30,
            variable=self.fps_var,
            orient=tk.HORIZONTAL,
            length=150
        ).pack(side=tk.LEFT, padx=(5, 10))

        self.fps_label = ttk.Label(speed_row, text="10")
        self.fps_label.pack(side=tk.LEFT)
        self.fps_var.trace_add('write', lambda *a: self.fps_label.config(text=str(self.fps_var.get())))

        # Duration
        duration_row = ttk.Frame(options_frame)
        duration_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(duration_row, text="Duration:").pack(side=tk.LEFT)
        self.duration_var = tk.IntVar(value=0)
        ttk.Spinbox(
            duration_row,
            from_=0,
            to=300,
            textvariable=self.duration_var,
            width=5
        ).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(duration_row, text="seconds (0 = infinite)").pack(side=tk.LEFT)

        # Game of Life density (shown only for GoL)
        self.gol_frame = ttk.Frame(options_frame)

        ttk.Label(self.gol_frame, text="Initial Density:").pack(side=tk.LEFT)
        self.density_var = tk.DoubleVar(value=0.3)
        ttk.Scale(
            self.gol_frame,
            from_=0.1,
            to=0.5,
            variable=self.density_var,
            orient=tk.HORIZONTAL,
            length=100
        ).pack(side=tk.LEFT, padx=(5, 0))

        self._on_type_change()

        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            self.tab_frame,
            textvariable=self.status_var,
            foreground="gray"
        ).pack(anchor=tk.W, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(self.tab_frame)
        button_frame.pack(fill=tk.X)

        self.send_button = ttk.Button(
            button_frame,
            text="Start Animation",
            command=self.send_to_display
        )
        self.send_button.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop",
            command=self.stop,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Save as Preset",
            command=self._save_preset
        ).pack(side=tk.LEFT)

        return self.tab_frame

    def _on_type_change(self) -> None:
        """Handle animation type change."""
        anim_type = self.type_var.get()

        # Show/hide GoL density option
        if anim_type == AnimationType.GAME_OF_LIFE:
            self.gol_frame.pack(fill=tk.X, pady=(0, 10))
        else:
            self.gol_frame.pack_forget()

    def send_to_display(self) -> bool:
        """Start animation."""
        if not self.require_connection():
            return False

        self.stop_other_features()
        self.set_active()

        # Reset animation state
        self.anim_state = AnimationState()
        self.frame_num = 0
        self.state.animation_running = True

        # Update UI
        self.send_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Running...")

        # Calculate duration
        duration = self.duration_var.get()
        if duration > 0:
            total_frames = duration * self.fps_var.get()
        else:
            total_frames = float('inf')

        # Start animation loop
        self._animate_frame(total_frames)

        return True

    def _animate_frame(self, total_frames: float) -> None:
        """Generate and send one animation frame."""
        if not self.state.animation_running:
            return

        if self.frame_num >= total_frames:
            self.stop()
            return

        # Generate frame
        anim_type = self.type_var.get()
        color_scheme = self.color_var.get()

        options = {}
        if anim_type == AnimationType.GAME_OF_LIFE:
            options['density'] = self.density_var.get()

        img = self.generator.generate_frame(
            anim_type,
            self.frame_num,
            color_scheme,
            self.anim_state,
            **options
        )

        # Send to display
        from ..utils.image_utils import save_temp_image
        path = save_temp_image(img, 'ipixel_anim.png')
        self.device.send_image(path, resize_method='crop', save_slot=0)

        self.frame_num += 1

        # Update status
        if total_frames != float('inf'):
            remaining = int((total_frames - self.frame_num) / self.fps_var.get())
            self.status_var.set(f"Frame {self.frame_num}/{int(total_frames)} ({remaining}s remaining)")
        else:
            self.status_var.set(f"Frame {self.frame_num}")

        # Schedule next frame
        if self.state.animation_running:
            interval = 1000 // self.fps_var.get()
            self.timers.schedule(TimerNames.ANIMATION_FRAME, interval,
                lambda: self._animate_frame(total_frames))

    def stop(self) -> None:
        """Stop animation."""
        self.state.animation_running = False
        self.timers.cancel(TimerNames.ANIMATION_FRAME)

        self.send_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Stopped")

    def _save_preset(self) -> None:
        """Save as preset."""
        from ..ui.widgets.preset_dialog import PresetSaveDialog

        anim_type = self.type_var.get()
        type_names = {v: n for n, v in self.ANIMATION_TYPES}
        default_name = f"Animation - {type_names.get(anim_type, 'Unknown')}"

        PresetSaveDialog(
            parent=self.root,
            preset_type="Animation",
            default_name=default_name,
            on_create=self.create_preset,
            on_complete=lambda p: self.config.add_preset(p)
        )

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Create preset."""
        return {
            'name': name,
            'type': self.feature_id,
            'anim_type': self.type_var.get(),
            'color_scheme': self.color_var.get(),
            'fps': self.fps_var.get(),
            'duration': self.duration_var.get(),
            'density': self.density_var.get(),
        }

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute preset."""
        self.type_var.set(preset.get('anim_type', AnimationType.GAME_OF_LIFE))
        self.color_var.set(preset.get('color_scheme', ColorScheme.GREEN))
        self.fps_var.set(preset.get('fps', 10))
        self.duration_var.set(preset.get('duration', 0))
        self.density_var.set(preset.get('density', 0.3))

        self._on_type_change()
        return self.send_to_display()

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """Get preset preview."""
        anim_type = preset.get('anim_type', '')
        type_names = {v: n for n, v in self.ANIMATION_TYPES}
        return type_names.get(anim_type, 'Animation')
