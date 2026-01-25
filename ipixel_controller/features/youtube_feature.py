"""
YouTube stats display feature.

Displays YouTube channel subscriber counts and statistics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from .base import FeatureBase
from ..ui.widgets.color_picker import ColorPickerWidget
from ..ui.widgets.sprite_font_selector import SpriteFontSelector
from ..ui.widgets.auto_refresh_control import AutoRefreshControl
from ..core.timers import TimerNames
from ..services.youtube_service import format_youtube_display


class YouTubeFeature(FeatureBase):
    """
    YouTube stats display feature.

    Shows channel subscriber counts with:
    - Channel lookup by handle or ID
    - Optional logo display
    - Sprite font rendering
    - Auto-refresh support
    """

    feature_id = "youtube"
    display_name = "YouTube"
    tab_icon = "📺"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_color = "#FFFFFF"
        self.current_data: Optional[Dict[str, Any]] = None

    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """Create the YouTube tab UI."""
        self.tab_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.tab_frame, text=self.tab_title)

        # API Key setup
        api_frame = ttk.LabelFrame(self.tab_frame, text="API Setup", padding="10")
        api_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            api_frame,
            text="Get free API key from: console.cloud.google.com",
            foreground="blue"
        ).pack(anchor=tk.W)

        key_row = ttk.Frame(api_frame)
        key_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(key_row, text="API Key:").pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(
            value=self.config.get_secret('youtube_api_key', '')
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

        # Channel input
        channel_frame = ttk.LabelFrame(self.tab_frame, text="Channel", padding="10")
        channel_frame.pack(fill=tk.X, pady=(0, 10))

        channel_row = ttk.Frame(channel_frame)
        channel_row.pack(fill=tk.X)

        ttk.Label(channel_row, text="Channel:").pack(side=tk.LEFT)
        self.channel_var = tk.StringVar(value="@MrBeast")
        ttk.Entry(
            channel_row,
            textvariable=self.channel_var,
            width=30
        ).pack(side=tk.LEFT, padx=(5, 10))

        self.fetch_button = ttk.Button(
            channel_row,
            text="Fetch Stats",
            command=self._fetch_data
        )
        self.fetch_button.pack(side=tk.LEFT)

        # Status
        self.status_var = tk.StringVar(value="Enter channel and fetch stats")
        ttk.Label(
            channel_frame,
            textvariable=self.status_var,
            foreground="gray"
        ).pack(anchor=tk.W, pady=(10, 0))

        # Display options
        options_frame = ttk.LabelFrame(self.tab_frame, text="Display Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        # Background color
        color_row = ttk.Frame(options_frame)
        color_row.pack(fill=tk.X, pady=(0, 10))

        self.bg_picker = ColorPickerWidget(
            color_row,
            label="Background:",
            initial_color=self.bg_color,
            on_change=lambda c: setattr(self, 'bg_color', c)
        )
        self.bg_picker.pack(side=tk.LEFT)

        # Logo option
        logo_row = ttk.Frame(options_frame)
        logo_row.pack(fill=tk.X, pady=(0, 10))

        self.show_logo_var = tk.BooleanVar(
            value=self.state.settings.get('youtube_show_logo', True)
        )
        ttk.Checkbutton(
            logo_row,
            text="Show YouTube logo before stats",
            variable=self.show_logo_var
        ).pack(side=tk.LEFT)

        # Logo delay
        ttk.Label(logo_row, text="Logo delay:").pack(side=tk.LEFT, padx=(20, 5))
        self.logo_delay_var = tk.IntVar(
            value=self.state.settings.get('youtube_logo_delay_seconds', 2)
        )
        ttk.Spinbox(
            logo_row,
            from_=1,
            to=10,
            textvariable=self.logo_delay_var,
            width=5
        ).pack(side=tk.LEFT)
        ttk.Label(logo_row, text="sec").pack(side=tk.LEFT, padx=(5, 0))

        # Sprite font
        self.use_sprite_var = tk.BooleanVar(
            value=self.state.settings.get('youtube_use_sprite_font', True)
        )
        self.sprite_font_var = tk.StringVar(
            value=self.state.settings.get('youtube_sprite_font_name', '')
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
        self.refresh_interval_var = tk.IntVar(value=300)  # 5 minutes

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
        """Save API key."""
        key = self.api_key_var.get().strip()
        self.config.set_secret('youtube_api_key', key)
        messagebox.showinfo("Saved", "API key saved!")

    def _fetch_data(self) -> None:
        """Fetch YouTube stats."""
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("No API Key", "Please enter your YouTube API key.")
            return

        channel = self.channel_var.get().strip()
        if not channel:
            messagebox.showwarning("No Channel", "Please enter a channel ID or @handle.")
            return

        self.status_var.set(f"Fetching stats for {channel}...")
        self.fetch_button.config(state=tk.DISABLED)

        # Get or create YouTube service
        yt_service = self.services.get('youtube')
        if not yt_service:
            from ..services.youtube_service import YouTubeService
            yt_service = YouTubeService(
                self.root,
                self._on_data_fetched,
                self._on_fetch_error,
                api_key=api_key
            )
            self.services['youtube'] = yt_service
        else:
            yt_service.set_api_key(api_key)
            yt_service._on_success = self._on_data_fetched
            yt_service._on_error = self._on_fetch_error

        yt_service.fetch(channel=channel)

    def _on_data_fetched(self, data: Dict[str, Any]) -> None:
        """Handle fetched data."""
        self.current_data = data
        self.fetch_button.config(state=tk.NORMAL)

        subs = data.get('subscriber_count', 0)
        title = data.get('title', 'Unknown')

        # Format subscriber count
        from ..services.youtube_service import _format_large_number
        subs_str = _format_large_number(subs)

        self.status_var.set(f"{title}: {subs_str} subscribers")

    def _on_fetch_error(self, error: str) -> None:
        """Handle fetch error."""
        self.fetch_button.config(state=tk.NORMAL)
        self.status_var.set(f"Error: {error}")
        messagebox.showerror("Fetch Error", error)

    def send_to_display(self) -> bool:
        """Send YouTube stats to display."""
        if not self.require_connection():
            return False

        if not self.current_data:
            messagebox.showwarning("No Data", "Please fetch stats first.")
            return False

        self.stop_other_features()
        self.set_active()

        # Show logo first if enabled
        if self.show_logo_var.get():
            self._show_logo_then_stats()
        else:
            self._show_stats()

        # Setup auto-refresh
        if self.refresh_enabled_var.get():
            self._schedule_refresh()

        return True

    def _show_logo_then_stats(self) -> None:
        """Show logo on left with stats on right."""
        self._show_stats_with_logo()

    def _show_stats_with_logo(self) -> None:
        """Display logo on left with subscriber stats on right."""
        from PIL import Image
        from ..utils.paths import resolve_asset_path
        from ..utils.image_utils import save_temp_image

        display_text = format_youtube_display(self.current_data, 'subscribers')

        # Create base canvas
        canvas = Image.new('RGB', (64, 16), self.bg_color)

        # Load and add logo on left
        logo_path = self.state.settings.get(
            'youtube_logo_path',
            'Gallery/Sprites/YT-btn.png'
        )
        resolved = resolve_asset_path(logo_path)

        logo_width = 0
        import os
        if os.path.isfile(resolved):
            try:
                with Image.open(resolved) as logo:
                    # Scale logo to fit height (16px)
                    if logo.height != 16:
                        ratio = 16 / logo.height
                        new_width = int(logo.width * ratio)
                        logo = logo.resize((new_width, 16), Image.LANCZOS)

                    # Convert to RGB/RGBA for pasting
                    if logo.mode == 'P':
                        logo = logo.convert('RGBA')

                    logo_width = logo.width

                    # Paste logo on left (with transparency if available)
                    if logo.mode == 'RGBA':
                        canvas.paste(logo, (0, 0), logo)
                    else:
                        canvas.paste(logo, (0, 0))
            except Exception as e:
                print(f"Error loading YouTube logo: {e}")

        # Render stats text
        text_start_x = logo_width + 2 if logo_width > 0 else 0
        available_width = 64 - text_start_x

        if self.use_sprite_var.get() and available_width > 0:
            sprite_service = self.services.get('sprite_font')
            if sprite_service:
                # Render text as line (not fixed size)
                text_img, error = sprite_service.render_text_line(
                    display_text,
                    self.sprite_font_var.get(),
                    self.bg_color
                )
                if not error and text_img:
                    # If text fits, paste it; if not, crop to fit
                    if text_img.width <= available_width:
                        # Center text in available space
                        text_x = text_start_x + (available_width - text_img.width) // 2
                        text_y = (16 - text_img.height) // 2
                        if text_img.mode == 'RGBA':
                            canvas.paste(text_img, (text_x, text_y), text_img)
                        else:
                            canvas.paste(text_img.convert('RGB'), (text_x, text_y))
                    else:
                        # Crop text to fit
                        cropped = text_img.crop((0, 0, available_width, text_img.height))
                        text_y = (16 - cropped.height) // 2
                        if cropped.mode == 'RGBA':
                            canvas.paste(cropped, (text_start_x, text_y), cropped)
                        else:
                            canvas.paste(cropped.convert('RGB'), (text_start_x, text_y))

                    path = save_temp_image(canvas, 'ipixel_youtube.png')
                    self.device.send_image(path, resize_method='crop', save_slot=0)
                    return

        # Fallback - just save canvas with logo
        if logo_width > 0:
            path = save_temp_image(canvas, 'ipixel_youtube.png')
            self.device.send_image(path, resize_method='crop', save_slot=0)
        else:
            # No logo, use regular text
            self.device.send_text(
                display_text,
                char_height=16,
                color="#FF0000",
                bg_color=self.bg_color,
                animation=0,
                speed=50
            )

    def _show_stats(self) -> None:
        """Display subscriber stats (without logo)."""
        display_text = format_youtube_display(self.current_data, 'subscribers')

        if self.use_sprite_var.get():
            sprite_service = self.services.get('sprite_font')
            if sprite_service:
                img, error = sprite_service.render_text_fixed(
                    display_text,
                    self.sprite_font_var.get(),
                    self.bg_color
                )
                if not error:
                    from ..utils.image_utils import save_temp_image
                    path = save_temp_image(img, 'ipixel_youtube.png')
                    self.device.send_image(path, resize_method='crop', save_slot=0)
                    return

        # Fallback to text
        self.device.send_text(
            display_text,
            char_height=16,
            color="#FF0000",  # YouTube red
            bg_color=self.bg_color,
            animation=0,
            speed=50
        )

    def _schedule_refresh(self) -> None:
        """Schedule auto-refresh."""
        def refresh():
            self._fetch_data()
            self.root.after(2000, self.send_to_display)

        interval = self.refresh_interval_var.get() * 1000
        self.timers.schedule(TimerNames.YOUTUBE_REFRESH, interval, refresh)

    def stop(self) -> None:
        """Stop auto-refresh."""
        self.timers.cancel(TimerNames.YOUTUBE_REFRESH)
        self.timers.cancel(TimerNames.YOUTUBE_LOGO_DELAY)

    def _save_preset(self) -> None:
        """Save as preset."""
        from ..ui.widgets.preset_dialog import PresetSaveDialog

        channel = self.channel_var.get() or "YouTube"
        PresetSaveDialog(
            parent=self.root,
            preset_type="YouTube",
            default_name=f"YouTube - {channel}",
            on_create=self.create_preset,
            on_complete=lambda p: self.config.add_preset(p)
        )

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Create preset."""
        return {
            'name': name,
            'type': self.feature_id,
            'channel': self.channel_var.get(),
            'bg_color': self.bg_color,
            'youtube_show_logo': self.show_logo_var.get(),
            'youtube_logo_delay_seconds': self.logo_delay_var.get(),
            'youtube_use_sprite_font': self.use_sprite_var.get(),
            'youtube_sprite_font_name': self.sprite_font_var.get(),
            'auto_refresh': self.refresh_enabled_var.get(),
            'refresh_interval': self.refresh_interval_var.get(),
        }

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute preset."""
        self.channel_var.set(preset.get('channel', ''))
        self.bg_color = preset.get('bg_color', '#FFFFFF')
        self.bg_picker.set_color(self.bg_color)
        self.show_logo_var.set(preset.get('youtube_show_logo', True))
        self.logo_delay_var.set(preset.get('youtube_logo_delay_seconds', 2))
        self.use_sprite_var.set(preset.get('youtube_use_sprite_font', True))
        self.sprite_font_var.set(preset.get('youtube_sprite_font_name', ''))
        self.refresh_enabled_var.set(preset.get('auto_refresh', False))
        self.refresh_interval_var.set(preset.get('refresh_interval', 300))

        self._fetch_data()
        self.root.after(2000, self.send_to_display)
        return True

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """Get preset preview."""
        return preset.get('channel', 'YouTube')
