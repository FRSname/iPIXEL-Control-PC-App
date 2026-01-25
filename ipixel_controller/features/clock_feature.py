"""
Clock display feature.

Displays time using built-in clock modes or custom sprite fonts.
Also includes countdown timer functionality.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any
from datetime import datetime, timedelta

from .base import FeatureBase
from ..ui.widgets.color_picker import DualColorPickerWidget
from ..ui.widgets.sprite_font_selector import SpriteFontSelector
from ..core.timers import TimerNames


class ClockFeature(FeatureBase):
    """
    Clock display feature.

    Supports:
    - Built-in clock styles (0-8)
    - Custom time formats with sprite fonts
    - Countdown timers to specific dates
    """

    feature_id = "clock"
    display_name = "Clock"
    tab_icon = "🕐"

    CLOCK_MODES = ["Built-in", "Custom", "Countdown"]
    BUILTIN_STYLES = list(range(9))  # 0-8
    TIME_FORMATS = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%H.%M"]
    COUNTDOWN_FORMATS = [
        ("Days Hours Mins", "days_hours_mins"),
        ("Hours Mins Secs", "hours_mins_secs"),
        ("Days Only", "days_only"),
        ("Full", "full"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clock_color = "#FFFFFF"
        self.clock_bg_color = "#000000"
        self.countdown_color = "#00FF00"
        self.countdown_bg_color = "#000000"

    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """Create the clock tab UI."""
        self.tab_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.tab_frame, text=self.tab_title)

        # Mode selection
        mode_frame = ttk.LabelFrame(self.tab_frame, text="Clock Mode", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.mode_var = tk.StringVar(value="Built-in")
        for i, mode in enumerate(self.CLOCK_MODES):
            ttk.Radiobutton(
                mode_frame,
                text=mode,
                variable=self.mode_var,
                value=mode,
                command=self._on_mode_change
            ).pack(side=tk.LEFT, padx=(0, 20))

        # Container for mode-specific options
        self.options_container = ttk.Frame(self.tab_frame)
        self.options_container.pack(fill=tk.BOTH, expand=True)

        # Create mode frames
        self._create_builtin_frame()
        self._create_custom_frame()
        self._create_countdown_frame()

        # Show initial mode
        self._on_mode_change()

        # Buttons
        button_frame = ttk.Frame(self.tab_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.send_button = self._create_send_button(button_frame, "Show Clock")
        self.send_button.pack(side=tk.LEFT, padx=(0, 10))

        self.live_button = ttk.Button(
            button_frame,
            text="Start Live Clock",
            command=self._toggle_live_clock
        )
        self.live_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Stop",
            command=self.stop
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Save as Preset",
            command=self._save_preset
        ).pack(side=tk.LEFT)

        return self.tab_frame

    def _create_builtin_frame(self) -> None:
        """Create built-in clock options."""
        self.builtin_frame = ttk.LabelFrame(
            self.options_container, text="Built-in Clock", padding="10"
        )

        ttk.Label(self.builtin_frame, text="Style:").pack(anchor=tk.W)
        self.style_var = tk.IntVar(value=0)

        style_frame = ttk.Frame(self.builtin_frame)
        style_frame.pack(fill=tk.X, pady=(5, 0))

        for style in self.BUILTIN_STYLES:
            ttk.Radiobutton(
                style_frame,
                text=str(style),
                variable=self.style_var,
                value=style
            ).pack(side=tk.LEFT, padx=(0, 10))

    def _create_custom_frame(self) -> None:
        """Create custom clock options."""
        self.custom_frame = ttk.LabelFrame(
            self.options_container, text="Custom Clock", padding="10"
        )

        # Time format
        ttk.Label(self.custom_frame, text="Format:").pack(anchor=tk.W)
        self.format_var = tk.StringVar(value=self.TIME_FORMATS[0])
        format_combo = ttk.Combobox(
            self.custom_frame,
            values=self.TIME_FORMATS,
            textvariable=self.format_var,
            state="readonly",
            width=20
        )
        format_combo.pack(anchor=tk.W, pady=(5, 10))

        # Colors
        self.clock_colors = DualColorPickerWidget(
            self.custom_frame,
            text_label="Time Color:",
            bg_label="Background:",
            text_color=self.clock_color,
            bg_color=self.clock_bg_color,
            on_text_change=lambda c: setattr(self, 'clock_color', c),
            on_bg_change=lambda c: setattr(self, 'clock_bg_color', c)
        )
        self.clock_colors.pack(anchor=tk.W, pady=(0, 10))

        # Sprite font
        self.clock_use_sprite_var = tk.BooleanVar(
            value=self.state.settings.get('clock_use_time_sprite', False)
        )
        self.clock_sprite_var = tk.StringVar(
            value=self.state.settings.get('clock_time_sprite_font_name', 'Clock Default')
        )

        self.clock_sprite_selector = SpriteFontSelector(
            self.custom_frame,
            font_names=self.config.get_sprite_font_names(),
            use_sprite_var=self.clock_use_sprite_var,
            font_name_var=self.clock_sprite_var
        )
        self.clock_sprite_selector.pack(anchor=tk.W, pady=(0, 10))

        # Update interval
        interval_frame = ttk.Frame(self.custom_frame)
        interval_frame.pack(anchor=tk.W)
        ttk.Label(interval_frame, text="Update every:").pack(side=tk.LEFT)
        self.update_interval_var = tk.IntVar(value=1)
        ttk.Spinbox(
            interval_frame,
            from_=1,
            to=60,
            textvariable=self.update_interval_var,
            width=5
        ).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(interval_frame, text="seconds").pack(side=tk.LEFT, padx=(5, 0))

    def _create_countdown_frame(self) -> None:
        """Create countdown timer options."""
        self.countdown_frame = ttk.LabelFrame(
            self.options_container, text="Countdown Timer", padding="10"
        )

        # Event name
        ttk.Label(self.countdown_frame, text="Event Name:").pack(anchor=tk.W)
        self.event_var = tk.StringVar(value="Event")
        ttk.Entry(
            self.countdown_frame,
            textvariable=self.event_var,
            width=30
        ).pack(anchor=tk.W, pady=(5, 10))

        # Target date/time
        ttk.Label(self.countdown_frame, text="Target Date/Time:").pack(anchor=tk.W)
        date_frame = ttk.Frame(self.countdown_frame)
        date_frame.pack(anchor=tk.W, pady=(5, 10))

        now = datetime.now()
        self.year_var = tk.IntVar(value=now.year)
        self.month_var = tk.IntVar(value=now.month)
        self.day_var = tk.IntVar(value=now.day)
        self.hour_var = tk.IntVar(value=0)
        self.minute_var = tk.IntVar(value=0)

        ttk.Spinbox(date_frame, from_=2024, to=2030, textvariable=self.year_var, width=6).pack(side=tk.LEFT)
        ttk.Label(date_frame, text="-").pack(side=tk.LEFT)
        ttk.Spinbox(date_frame, from_=1, to=12, textvariable=self.month_var, width=4).pack(side=tk.LEFT)
        ttk.Label(date_frame, text="-").pack(side=tk.LEFT)
        ttk.Spinbox(date_frame, from_=1, to=31, textvariable=self.day_var, width=4).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" ").pack(side=tk.LEFT)
        ttk.Spinbox(date_frame, from_=0, to=23, textvariable=self.hour_var, width=4).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=":").pack(side=tk.LEFT)
        ttk.Spinbox(date_frame, from_=0, to=59, textvariable=self.minute_var, width=4).pack(side=tk.LEFT)

        # Format
        ttk.Label(self.countdown_frame, text="Display Format:").pack(anchor=tk.W)
        self.countdown_format_var = tk.StringVar(value="days_hours_mins")
        format_combo = ttk.Combobox(
            self.countdown_frame,
            values=[f[0] for f in self.COUNTDOWN_FORMATS],
            state="readonly",
            width=20
        )
        format_combo.current(0)
        format_combo.pack(anchor=tk.W, pady=(5, 10))
        format_combo.bind('<<ComboboxSelected>>',
            lambda e: self.countdown_format_var.set(self.COUNTDOWN_FORMATS[format_combo.current()][1]))

        # Colors
        self.countdown_colors = DualColorPickerWidget(
            self.countdown_frame,
            text_color=self.countdown_color,
            bg_color=self.countdown_bg_color,
            on_text_change=lambda c: setattr(self, 'countdown_color', c),
            on_bg_change=lambda c: setattr(self, 'countdown_bg_color', c)
        )
        self.countdown_colors.pack(anchor=tk.W)

    def _on_mode_change(self) -> None:
        """Handle clock mode change."""
        # Hide all frames
        self.builtin_frame.pack_forget()
        self.custom_frame.pack_forget()
        self.countdown_frame.pack_forget()

        # Show selected frame
        mode = self.mode_var.get()
        if mode == "Built-in":
            self.builtin_frame.pack(fill=tk.BOTH, expand=True)
        elif mode == "Custom":
            self.custom_frame.pack(fill=tk.BOTH, expand=True)
        elif mode == "Countdown":
            self.countdown_frame.pack(fill=tk.BOTH, expand=True)

    def send_to_display(self) -> bool:
        """Send clock to display."""
        if not self.require_connection():
            return False

        self.stop_other_features()
        self.set_active()

        mode = self.mode_var.get()
        if mode == "Built-in":
            return self._show_builtin_clock()
        elif mode == "Custom":
            return self._show_custom_clock()
        elif mode == "Countdown":
            return self._start_countdown()

        return False

    def _show_builtin_clock(self) -> bool:
        """Show built-in clock style."""
        style = self.style_var.get()
        self.device.set_clock_mode(style=style)
        return True

    def _show_custom_clock(self) -> bool:
        """Show custom formatted clock."""
        time_str = datetime.now().strftime(self.format_var.get())
        return self._send_time_text(time_str, self.clock_color, self.clock_bg_color)

    def _send_time_text(self, text: str, color: str, bg_color: str) -> bool:
        """Send time text to display."""
        if self.clock_use_sprite_var.get():
            sprite_service = self.services.get('sprite_font')
            if sprite_service:
                img, error = sprite_service.render_text_fixed(
                    text, self.clock_sprite_var.get(), bg_color
                )
                if not error:
                    from ..utils.image_utils import save_temp_image
                    path = save_temp_image(img, 'ipixel_clock.png')
                    self.device.send_image(path, resize_method='crop', save_slot=0)
                    return True

        # Fallback to regular text
        self.device.send_text(
            text,
            char_height=16,
            color=color,
            bg_color=bg_color,
            animation=0,
            speed=50
        )
        return True

    def _toggle_live_clock(self) -> None:
        """Toggle live clock updates."""
        if self.state.clock_running:
            self.stop()
            self.live_button.config(text="Start Live Clock")
        else:
            self._start_live_clock()
            self.live_button.config(text="Stop Live Clock")

    def _start_live_clock(self) -> None:
        """Start live updating clock."""
        if not self.require_connection():
            return

        self.stop_other_features()
        self.set_active()
        self.state.clock_running = True

        def tick():
            if not self.state.clock_running:
                return

            mode = self.mode_var.get()
            if mode == "Custom":
                self._show_custom_clock()
            elif mode == "Countdown":
                self._update_countdown()

            if self.state.clock_running:
                interval = self.update_interval_var.get() * 1000
                self.timers.schedule(TimerNames.CLOCK_UPDATE, interval, tick)

        tick()

    def _start_countdown(self) -> bool:
        """Start countdown timer."""
        self.state.clock_running = True
        self._update_countdown()

        def tick():
            if not self.state.clock_running:
                return
            self._update_countdown()
            if self.state.clock_running:
                self.timers.schedule(TimerNames.COUNTDOWN_UPDATE, 1000, tick)

        self.timers.schedule(TimerNames.COUNTDOWN_UPDATE, 1000, tick)
        return True

    def _update_countdown(self) -> None:
        """Update countdown display."""
        target = datetime(
            self.year_var.get(),
            self.month_var.get(),
            self.day_var.get(),
            self.hour_var.get(),
            self.minute_var.get()
        )
        remaining = target - datetime.now()

        if remaining.total_seconds() <= 0:
            text = "NOW!"
        else:
            text = self._format_countdown(remaining)

        self._send_time_text(text, self.countdown_color, self.countdown_bg_color)

    def _format_countdown(self, delta: timedelta) -> str:
        """Format countdown timedelta."""
        total_seconds = int(delta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        mins = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        fmt = self.countdown_format_var.get()
        if fmt == "days_hours_mins":
            return f"{days}d {hours}h {mins}m"
        elif fmt == "hours_mins_secs":
            return f"{hours}:{mins:02d}:{secs:02d}"
        elif fmt == "days_only":
            return f"{days} days"
        else:  # full
            return f"{days}d {hours}:{mins:02d}:{secs:02d}"

    def stop(self) -> None:
        """Stop clock updates."""
        self.state.clock_running = False
        self.timers.cancel(TimerNames.CLOCK_UPDATE)
        self.timers.cancel(TimerNames.COUNTDOWN_UPDATE)
        self.live_button.config(text="Start Live Clock")

    def _save_preset(self) -> None:
        """Save current settings as preset."""
        from ..ui.widgets.preset_dialog import PresetSaveDialog

        mode = self.mode_var.get()
        default_name = f"Clock - {mode}"
        if mode == "Countdown":
            default_name = f"Countdown - {self.event_var.get()}"

        PresetSaveDialog(
            parent=self.root,
            preset_type="Clock",
            default_name=default_name,
            on_create=self.create_preset,
            on_complete=lambda p: self.config.add_preset(p)
        )

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Create preset from current state."""
        mode = self.mode_var.get()
        preset = {
            'name': name,
            'type': self.feature_id,
            'clock_mode': mode.lower(),
        }

        if mode == "Built-in":
            preset['clock_style'] = self.style_var.get()
        elif mode == "Custom":
            preset.update({
                'time_format': self.format_var.get(),
                'clock_color': self.clock_color,
                'clock_bg_color': self.clock_bg_color,
                'clock_use_time_sprite': self.clock_use_sprite_var.get(),
                'clock_time_sprite_font_name': self.clock_sprite_var.get(),
                'clock_update_interval': self.update_interval_var.get(),
            })
        elif mode == "Countdown":
            preset.update({
                'countdown_event': self.event_var.get(),
                'countdown_year': self.year_var.get(),
                'countdown_month': self.month_var.get(),
                'countdown_day': self.day_var.get(),
                'countdown_hour': self.hour_var.get(),
                'countdown_minute': self.minute_var.get(),
                'countdown_format': self.countdown_format_var.get(),
                'countdown_color': self.countdown_color,
                'countdown_bg_color': self.countdown_bg_color,
            })

        return preset

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute a saved preset."""
        mode = preset.get('clock_mode', 'built-in')

        if mode == 'built-in':
            self.mode_var.set("Built-in")
            self.style_var.set(preset.get('clock_style', 0))
        elif mode == 'custom':
            self.mode_var.set("Custom")
            self.format_var.set(preset.get('time_format', '%H:%M'))
            self.clock_color = preset.get('clock_color', '#FFFFFF')
            self.clock_bg_color = preset.get('clock_bg_color', '#000000')
            self.clock_use_sprite_var.set(preset.get('clock_use_time_sprite', False))
            self.clock_sprite_var.set(preset.get('clock_time_sprite_font_name', ''))
            self.update_interval_var.set(preset.get('clock_update_interval', 1))
        elif mode == 'countdown':
            self.mode_var.set("Countdown")
            self.event_var.set(preset.get('countdown_event', ''))
            self.year_var.set(preset.get('countdown_year', 2025))
            self.month_var.set(preset.get('countdown_month', 1))
            self.day_var.set(preset.get('countdown_day', 1))
            self.hour_var.set(preset.get('countdown_hour', 0))
            self.minute_var.set(preset.get('countdown_minute', 0))
            self.countdown_format_var.set(preset.get('countdown_format', 'days_hours_mins'))
            self.countdown_color = preset.get('countdown_color', '#00FF00')
            self.countdown_bg_color = preset.get('countdown_bg_color', '#000000')

        self._on_mode_change()

        # For custom and countdown modes, start the live update loop
        if mode == 'custom':
            self._start_live_clock()
            self.live_button.config(text="Stop Live Clock")
            return True
        elif mode == 'countdown':
            return self._start_countdown()
        else:
            # Built-in mode just needs send_to_display once
            return self.send_to_display()

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """Get preview for preset."""
        mode = preset.get('clock_mode', 'built-in')
        if mode == 'countdown':
            return preset.get('countdown_event', 'Countdown')
        return f"Clock ({mode})"
