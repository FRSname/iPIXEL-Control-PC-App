"""
Weather display feature.

Displays current weather conditions using OpenWeatherMap API.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from .base import FeatureBase
from ..ui.widgets.color_picker import ColorPickerWidget
from ..ui.widgets.sprite_font_selector import SpriteFontSelector
from ..ui.widgets.auto_refresh_control import AutoRefreshControl
from ..core.timers import TimerNames


class WeatherFeature(FeatureBase):
    """
    Weather display feature.

    Shows current weather conditions with:
    - Temperature and condition
    - Multiple display formats
    - Celsius/Fahrenheit support
    - Auto-refresh
    """

    feature_id = "weather"
    display_name = "Weather"
    tab_icon = "🌤️"

    FORMATS = [
        ("Temp + Condition", "temp_condition"),
        ("Temperature Only", "temp_only"),
        ("City + Temp", "city_temp"),
        ("Full Info", "full"),
    ]

    UNITS = [("Celsius", "metric"), ("Fahrenheit", "imperial")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_color = "#000000"
        self.text_color = "#FFFFFF"
        self.current_data: Optional[Dict[str, Any]] = None

    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """Create the weather tab UI."""
        self.tab_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.tab_frame, text=self.tab_title)

        # API Key setup
        api_frame = ttk.LabelFrame(self.tab_frame, text="API Setup", padding="10")
        api_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            api_frame,
            text="Get free API key from: openweathermap.org",
            foreground="blue"
        ).pack(anchor=tk.W)

        key_row = ttk.Frame(api_frame)
        key_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(key_row, text="API Key:").pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(
            value=self.config.get_secret('weather_api_key', '')
        )
        ttk.Entry(
            key_row,
            textvariable=self.api_key_var,
            width=40,
            show="*"
        ).pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(
            key_row,
            text="Save Key",
            command=self._save_api_key
        ).pack(side=tk.LEFT)

        # Location input
        location_frame = ttk.LabelFrame(self.tab_frame, text="Location", padding="10")
        location_frame.pack(fill=tk.X, pady=(0, 10))

        loc_row = ttk.Frame(location_frame)
        loc_row.pack(fill=tk.X)

        ttk.Label(loc_row, text="City:").pack(side=tk.LEFT)
        self.location_var = tk.StringVar(value="London")
        ttk.Entry(
            loc_row,
            textvariable=self.location_var,
            width=25
        ).pack(side=tk.LEFT, padx=(5, 10))

        ttk.Label(loc_row, text="Units:").pack(side=tk.LEFT)
        self.unit_var = tk.StringVar(value="metric")
        for text, value in self.UNITS:
            ttk.Radiobutton(
                loc_row,
                text=text,
                variable=self.unit_var,
                value=value
            ).pack(side=tk.LEFT, padx=(5, 0))

        # Fetch button and status
        fetch_row = ttk.Frame(location_frame)
        fetch_row.pack(fill=tk.X, pady=(10, 0))

        self.fetch_button = ttk.Button(
            fetch_row,
            text="Fetch Weather",
            command=self._fetch_data
        )
        self.fetch_button.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Enter location and fetch")
        ttk.Label(
            fetch_row,
            textvariable=self.status_var,
            foreground="gray"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Display options
        options_frame = ttk.LabelFrame(self.tab_frame, text="Display Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        # Format
        format_row = ttk.Frame(options_frame)
        format_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(format_row, text="Format:").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value="temp_condition")
        format_combo = ttk.Combobox(
            format_row,
            values=[f[0] for f in self.FORMATS],
            state="readonly",
            width=20
        )
        format_combo.current(0)
        format_combo.pack(side=tk.LEFT, padx=(5, 0))
        format_combo.bind('<<ComboboxSelected>>',
            lambda e: self.format_var.set(self.FORMATS[format_combo.current()][1]))

        # Colors
        color_row = ttk.Frame(options_frame)
        color_row.pack(fill=tk.X, pady=(0, 10))

        self.text_picker = ColorPickerWidget(
            color_row,
            label="Text:",
            initial_color=self.text_color,
            on_change=lambda c: setattr(self, 'text_color', c)
        )
        self.text_picker.pack(side=tk.LEFT, padx=(0, 15))

        self.bg_picker = ColorPickerWidget(
            color_row,
            label="Background:",
            initial_color=self.bg_color,
            on_change=lambda c: setattr(self, 'bg_color', c)
        )
        self.bg_picker.pack(side=tk.LEFT)

        # Sprite font
        self.use_sprite_var = tk.BooleanVar(
            value=self.state.settings.get('weather_use_sprite_font', True)
        )
        self.sprite_font_var = tk.StringVar(
            value=self.state.settings.get('weather_sprite_font_name', '')
        )

        self.sprite_selector = SpriteFontSelector(
            options_frame,
            font_names=self.config.get_sprite_font_names(),
            use_sprite_var=self.use_sprite_var,
            font_name_var=self.sprite_font_var
        )
        self.sprite_selector.pack(anchor=tk.W, pady=(0, 10))

        # Auto-refresh
        self.refresh_enabled_var = tk.BooleanVar(value=False)
        self.refresh_interval_var = tk.IntVar(value=600)  # 10 minutes

        self.refresh_control = AutoRefreshControl(
            options_frame,
            enabled_var=self.refresh_enabled_var,
            interval_var=self.refresh_interval_var,
            min_interval=60,
            max_interval=3600,
            interval_step=60
        )
        self.refresh_control.pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(self.tab_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.send_button = self._create_send_button(button_frame, "Send to Display")
        self.send_button.pack(side=tk.LEFT, padx=(0, 10))

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

    def _save_api_key(self) -> None:
        """Save API key to secrets."""
        key = self.api_key_var.get().strip()
        self.config.set_secret('weather_api_key', key)
        messagebox.showinfo("Saved", "API key saved!")

    def _fetch_data(self) -> None:
        """Fetch weather data."""
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("No API Key", "Please enter your OpenWeatherMap API key.")
            return

        location = self.location_var.get().strip()
        if not location:
            messagebox.showwarning("No Location", "Please enter a city name.")
            return

        self.status_var.set(f"Fetching weather for {location}...")
        self.fetch_button.config(state=tk.DISABLED)

        # Get or create weather service
        weather_service = self.services.get('weather')
        if not weather_service:
            from ..services.weather_service import WeatherService
            weather_service = WeatherService(
                self.root,
                self._on_data_fetched,
                self._on_fetch_error,
                api_key=api_key
            )
            self.services['weather'] = weather_service
        else:
            weather_service.set_api_key(api_key)
            weather_service._on_success = self._on_data_fetched
            weather_service._on_error = self._on_fetch_error

        weather_service.fetch(location=location, units=self.unit_var.get())

    def _on_data_fetched(self, data: Dict[str, Any]) -> None:
        """Handle fetched data."""
        self.current_data = data
        self.fetch_button.config(state=tk.NORMAL)

        temp = data.get('temperature', 0)
        unit = data.get('temp_unit', '°C')
        condition = data.get('condition', '')

        self.status_var.set(f"{data.get('location')}: {temp}{unit} {condition}")

    def _on_fetch_error(self, error: str) -> None:
        """Handle fetch error."""
        self.fetch_button.config(state=tk.NORMAL)
        self.status_var.set(f"Error: {error}")
        messagebox.showerror("Fetch Error", error)

    def send_to_display(self) -> bool:
        """Send weather to display."""
        if not self.require_connection():
            return False

        if not self.current_data:
            messagebox.showwarning("No Data", "Please fetch weather data first.")
            return False

        self.stop_other_features()
        self.set_active()

        # Use custom icon-based display
        self._send_custom_weather_display()

        # Setup auto-refresh
        if self.refresh_enabled_var.get():
            self._schedule_refresh()

        return True

    def _get_weather_icon_filename(self, condition: str, icon_code: str) -> str:
        """
        Map OpenWeatherMap condition to local icon filename.

        Args:
            condition: Weather condition (e.g., "Rain", "Clouds", "Clear")
            icon_code: OpenWeatherMap icon code (e.g., "01d", "10n")

        Returns:
            Icon filename like "Rainy.png", "Sunny.png", etc.
        """
        condition_lower = condition.lower()

        # Map conditions to icons
        if condition_lower in ('thunderstorm',):
            return 'Thunderstorm.png'
        elif condition_lower in ('drizzle', 'rain'):
            return 'Rainy.png'
        elif condition_lower in ('snow',):
            return 'Snow.png'
        elif condition_lower in ('mist', 'smoke', 'haze', 'dust', 'fog', 'sand', 'ash', 'squall', 'tornado'):
            return 'Atmospheric.png'
        elif condition_lower == 'clouds':
            # Check icon code for cloud density
            if icon_code.startswith('02'):  # Few clouds
                return 'SunCloudy.png'
            else:  # Scattered, broken, overcast
                return 'Cloudy.png'
        elif condition_lower == 'clear':
            return 'Sunny.png'
        else:
            # Default fallback
            return 'Cloudy.png'

    def _send_custom_weather_display(self) -> None:
        """
        Send custom weather display with icons.

        Layout: [Weather Icon 16x16] [Temp Number] [Celsius.png 4x16] [Temp_plus/minus 11x16]
        """
        from PIL import Image
        import os
        from ..utils.paths import resolve_asset_path
        from ..utils.image_utils import save_temp_image

        # Create base canvas (64x16)
        canvas = Image.new('RGB', (64, 16), self.bg_color)

        temp = self.current_data.get('temperature', 0)
        condition = self.current_data.get('condition', 'Unknown')
        icon_code = self.current_data.get('icon', '')

        current_x = 0

        # 1. Weather condition icon (16x16) on the left
        weather_icon_file = self._get_weather_icon_filename(condition, icon_code)
        weather_icon_path = resolve_asset_path(f'Gallery/Sprites/{weather_icon_file}')

        if os.path.isfile(weather_icon_path):
            try:
                with Image.open(weather_icon_path) as icon:
                    icon = icon.convert('RGBA') if icon.mode != 'RGBA' else icon
                    # Resize to 16x16 if needed
                    if icon.size != (16, 16):
                        icon = icon.resize((16, 16), Image.LANCZOS)
                    canvas.paste(icon, (current_x, 0), icon)
            except Exception as e:
                print(f"Error loading weather icon: {e}")

        # Available space for temp number + celsius: from 16 (after weather icon) to 53 (before temp indicator)
        # That's 37 pixels of space
        available_start = 16
        available_end = 53
        available_width = available_end - available_start

        # 2. Temperature number (using sprite font) - always use absolute value
        temp_int = int(temp)
        temp_str = str(abs(temp_int))
        text_img = None
        text_width = 0
        minus_img = None
        minus_width = 0

        sprite_service = self.services.get('sprite_font')
        if sprite_service and self.use_sprite_var.get():
            font_name = self.sprite_font_var.get()
            text_img, error = sprite_service.render_text_line(
                temp_str,
                font_name,
                self.bg_color
            )
            if not error and text_img:
                text_width = text_img.width

            # Render minus sign separately if negative
            if temp_int < 0:
                minus_img, minus_error = sprite_service.render_text_line(
                    "-",
                    font_name,
                    self.bg_color
                )
                if not minus_error and minus_img:
                    minus_width = minus_img.width
        else:
            # Fallback: approximate width
            text_width = len(temp_str) * 7
            if temp_int < 0:
                minus_width = 7

        # 3. Load Celsius icon to get its width
        celsius_icon = None
        celsius_width = 4  # Default
        celsius_path = resolve_asset_path('Gallery/Sprites/Celsius.png')
        if os.path.isfile(celsius_path):
            try:
                celsius_icon = Image.open(celsius_path)
                celsius_icon = celsius_icon.convert('RGBA') if celsius_icon.mode != 'RGBA' else celsius_icon
                # Resize to 4x16 if needed
                if celsius_icon.size != (4, 16):
                    celsius_icon = celsius_icon.resize((4, 16), Image.LANCZOS)
                celsius_width = celsius_icon.width
            except Exception as e:
                print(f"Error loading Celsius icon: {e}")

        # Calculate centered position for temp number + spacing + celsius (minus is separate on left)
        spacing = 1  # 1 pixel gap between number and degree symbol
        total_content_width = text_width + spacing + celsius_width
        centered_start = available_start + (available_width - total_content_width) // 2

        # Paste minus sign on the left of the centered content (if negative)
        if temp_int < 0 and minus_img:
            minus_x = centered_start - minus_width - 1  # 1px gap before number
            minus_y = (16 - minus_img.height) // 2
            if minus_img.mode == 'RGBA':
                canvas.paste(minus_img, (minus_x, minus_y), minus_img)
            else:
                canvas.paste(minus_img.convert('RGB'), (minus_x, minus_y))

        # Paste temperature number centered
        if text_img:
            text_y = (16 - text_img.height) // 2
            if text_img.mode == 'RGBA':
                canvas.paste(text_img, (centered_start, text_y), text_img)
            else:
                canvas.paste(text_img.convert('RGB'), (centered_start, text_y))

        # Paste Celsius icon after the number with 1px gap
        if celsius_icon:
            canvas.paste(celsius_icon, (centered_start + text_width + spacing, 0), celsius_icon)
            celsius_icon.close()

        # 4. Temperature indicator - Temp_plus.png or Temp_minus.png (11x16) on the right
        if temp >= 0:
            temp_indicator_file = 'Temp_plus.png'
        else:
            temp_indicator_file = 'Temp_minus.png'

        temp_indicator_path = resolve_asset_path(f'Gallery/Sprites/{temp_indicator_file}')

        # Place temperature indicator on the right side of the display
        if os.path.isfile(temp_indicator_path):
            try:
                with Image.open(temp_indicator_path) as temp_icon:
                    temp_icon = temp_icon.convert('RGBA') if temp_icon.mode != 'RGBA' else temp_icon
                    # Resize to 11x16 if needed
                    if temp_icon.size != (11, 16):
                        temp_icon = temp_icon.resize((11, 16), Image.LANCZOS)
                    # Place on right side (64 - 11 = 53)
                    canvas.paste(temp_icon, (53, 0), temp_icon)
            except Exception as e:
                print(f"Error loading temp indicator icon: {e}")

        # Save and send to display
        path = save_temp_image(canvas, 'ipixel_weather.png')
        self.device.send_image(path, resize_method='crop', save_slot=0)

    def _schedule_refresh(self) -> None:
        """Schedule auto-refresh."""
        def refresh():
            self._fetch_data()
            self.root.after(2000, self.send_to_display)

        interval = self.refresh_interval_var.get() * 1000
        self.timers.schedule(TimerNames.WEATHER_REFRESH, interval, refresh)

    def stop(self) -> None:
        """Stop auto-refresh."""
        self.timers.cancel(TimerNames.WEATHER_REFRESH)

    def _save_preset(self) -> None:
        """Save as preset."""
        from ..ui.widgets.preset_dialog import PresetSaveDialog

        location = self.location_var.get() or "Weather"
        PresetSaveDialog(
            parent=self.root,
            preset_type="Weather",
            default_name=f"Weather - {location}",
            on_create=self.create_preset,
            on_complete=lambda p: self.config.add_preset(p)
        )

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Create preset."""
        return {
            'name': name,
            'type': self.feature_id,
            'location': self.location_var.get(),
            'unit': self.unit_var.get(),
            'format': self.format_var.get(),
            'text_color': self.text_color,
            'bg_color': self.bg_color,
            'auto_refresh': self.refresh_enabled_var.get(),
            'refresh_interval': self.refresh_interval_var.get(),
            'weather_use_sprite_font': self.use_sprite_var.get(),
            'weather_sprite_font_name': self.sprite_font_var.get(),
        }

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute preset."""
        self.location_var.set(preset.get('location', 'London'))
        self.unit_var.set(preset.get('unit', 'metric'))
        self.format_var.set(preset.get('format', 'temp_condition'))
        self.text_color = preset.get('text_color', '#FFFFFF')
        self.bg_color = preset.get('bg_color', '#000000')
        self.text_picker.set_color(self.text_color)
        self.bg_picker.set_color(self.bg_color)
        self.refresh_enabled_var.set(preset.get('auto_refresh', False))
        self.refresh_interval_var.set(preset.get('refresh_interval', 600))
        self.use_sprite_var.set(preset.get('weather_use_sprite_font', True))
        self.sprite_font_var.set(preset.get('weather_sprite_font_name', ''))

        self._fetch_data()
        self.root.after(2000, self.send_to_display)
        return True

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """Get preset preview."""
        return preset.get('location', 'Weather')
