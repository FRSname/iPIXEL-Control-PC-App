"""
Text display feature.

Allows displaying custom text with colors, animations, and sprite fonts.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from .base import FeatureBase
from ..ui.widgets.color_picker import DualColorPickerWidget
from ..ui.widgets.sprite_font_selector import SpriteFontSelector
from ..core.timers import TimerNames


class TextFeature(FeatureBase):
    """
    Text display feature.

    Allows users to display custom text on the LED panel with:
    - Custom text and background colors
    - Animation effects (static, scroll, blink)
    - Sprite font rendering
    - Rainbow mode
    """

    feature_id = "text"
    display_name = "Text"
    tab_icon = "📝"

    # Animation options
    ANIMATIONS = [
        ("Static", 0),
        ("Scroll Left", 1),
        ("Scroll Right", 2),
        ("Blink/Flash", 5),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_color = "#FFFFFF"
        self.bg_color = "#000000"

    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """Create the text tab UI."""
        self.tab_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.tab_frame, text=self.tab_title)

        # Text input
        text_frame = ttk.LabelFrame(self.tab_frame, text="Text", padding="10")
        text_frame.pack(fill=tk.X, pady=(0, 10))

        self.text_input = tk.Text(text_frame, height=3, width=50)
        self.text_input.pack(fill=tk.X)
        self.text_input.insert("1.0", "Hello World")

        # Colors
        color_frame = ttk.LabelFrame(self.tab_frame, text="Colors", padding="10")
        color_frame.pack(fill=tk.X, pady=(0, 10))

        self.color_picker = DualColorPickerWidget(
            color_frame,
            text_color=self.text_color,
            bg_color=self.bg_color,
            on_text_change=lambda c: setattr(self, 'text_color', c),
            on_bg_change=lambda c: setattr(self, 'bg_color', c)
        )
        self.color_picker.pack(anchor=tk.W)

        # Rainbow mode
        self.rainbow_var = tk.IntVar(value=0)
        ttk.Checkbutton(
            color_frame,
            text="Rainbow mode",
            variable=self.rainbow_var
        ).pack(anchor=tk.W, pady=(10, 0))

        # Animation
        anim_frame = ttk.LabelFrame(self.tab_frame, text="Animation", padding="10")
        anim_frame.pack(fill=tk.X, pady=(0, 10))

        anim_row = ttk.Frame(anim_frame)
        anim_row.pack(fill=tk.X)

        ttk.Label(anim_row, text="Effect:").pack(side=tk.LEFT)
        self.animation_var = tk.IntVar(value=0)
        anim_combo = ttk.Combobox(
            anim_row,
            values=[a[0] for a in self.ANIMATIONS],
            state="readonly",
            width=15
        )
        anim_combo.current(0)
        anim_combo.pack(side=tk.LEFT, padx=(5, 20))
        anim_combo.bind('<<ComboboxSelected>>',
            lambda e: self.animation_var.set(self.ANIMATIONS[anim_combo.current()][1]))

        ttk.Label(anim_row, text="Speed:").pack(side=tk.LEFT)
        self.speed_var = tk.IntVar(value=50)
        ttk.Scale(
            anim_row,
            from_=1,
            to=100,
            variable=self.speed_var,
            orient=tk.HORIZONTAL,
            length=150
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Sprite font
        sprite_frame = ttk.LabelFrame(self.tab_frame, text="Sprite Font", padding="10")
        sprite_frame.pack(fill=tk.X, pady=(0, 10))

        self.use_sprite_var = tk.BooleanVar(
            value=self.state.settings.get('text_use_sprite_font', False)
        )
        self.sprite_font_var = tk.StringVar(
            value=self.state.settings.get('text_sprite_font_name', '')
        )

        self.sprite_selector = SpriteFontSelector(
            sprite_frame,
            font_names=self.config.get_sprite_font_names(),
            use_sprite_var=self.use_sprite_var,
            font_name_var=self.sprite_font_var,
            on_change=self._on_sprite_change
        )
        self.sprite_selector.pack(anchor=tk.W)

        # Static delay for sprite
        delay_frame = ttk.Frame(sprite_frame)
        delay_frame.pack(anchor=tk.W, pady=(10, 0))
        ttk.Label(delay_frame, text="Static display delay:").pack(side=tk.LEFT)
        self.static_delay_var = tk.IntVar(
            value=self.state.settings.get('text_static_delay_seconds', 2)
        )
        ttk.Spinbox(
            delay_frame,
            from_=1,
            to=10,
            textvariable=self.static_delay_var,
            width=5
        ).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(delay_frame, text="seconds").pack(side=tk.LEFT, padx=(5, 0))

        # Buttons
        button_frame = ttk.Frame(self.tab_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.send_button = self._create_send_button(button_frame, "Send Text")
        self.send_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Save as Preset",
            command=self._save_preset
        ).pack(side=tk.LEFT)

        return self.tab_frame

    def _on_sprite_change(self) -> None:
        """Handle sprite font selection change."""
        self.config.set_setting('text_use_sprite_font', self.use_sprite_var.get())
        self.config.set_setting('text_sprite_font_name', self.sprite_font_var.get())

    def send_to_display(self) -> bool:
        """Send text to the display."""
        if not self.require_connection():
            return False

        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "Please enter some text.")
            return False

        # Stop other displays
        self.stop_other_features()
        self.set_active()

        # Check if using sprite font
        if self.use_sprite_var.get():
            return self._send_sprite_text(text)
        else:
            return self._send_regular_text(text)

    def _send_regular_text(self, text: str) -> bool:
        """Send text using device's built-in text rendering."""
        animation = self.animation_var.get()
        speed = 101 - self.speed_var.get()  # Invert speed

        self.device.send_text(
            text,
            char_height=16,
            color=self.text_color,
            bg_color=self.bg_color,
            animation=animation,
            speed=speed,
            rainbow_mode=self.rainbow_var.get()
        )
        return True

    def _send_sprite_text(self, text: str) -> bool:
        """Send text using sprite font rendering."""
        font_name = self.sprite_font_var.get()
        font = self.config.get_sprite_font_by_name(font_name)

        if not font:
            messagebox.showerror("Error", f"Sprite font '{font_name}' not found.")
            return False

        # Get sprite service
        sprite_service = self.services.get('sprite_font')
        if not sprite_service:
            messagebox.showerror("Error", "Sprite font service not available.")
            return False

        animation = self.animation_var.get()

        if animation in (1, 2):  # Scroll animation - scroll the full text
            img, error = sprite_service.render_text_line(
                text, font_name, self.bg_color
            )
            if error:
                messagebox.showerror("Error", error)
                return False
            self._start_sprite_scroll(img, animation == 2)
        else:
            # Static display - use pagination for long text
            self._send_sprite_text_paginated(text, font_name, font, sprite_service)

        return True

    def _send_sprite_text_paginated(self, text: str, font_name: str, font: dict, sprite_service) -> None:
        """Send sprite text with pagination for static display."""
        from PIL import Image
        from ..utils.image_utils import save_temp_image

        # Calculate max characters that fit in 64 pixels
        cols = font.get('cols', 73)
        # Load sprite to get actual tile width
        sprite_font = sprite_service.get_font(font_name)
        if sprite_font and sprite_font.load():
            tile_w = sprite_font.tile_width
        else:
            tile_w = 7  # Default fallback

        max_chars = max(1, 64 // tile_w)

        # Build pages from text
        pages = []
        words = text.split()

        current_page = ""
        for word in words:
            if not word:
                continue

            # If single word is longer than max_chars, it needs scrolling
            if len(word) > max_chars:
                # Save current page first if any
                if current_page:
                    pages.append({"text": current_page.strip(), "scroll": False})
                    current_page = ""
                # Add long word as scrolling page
                pages.append({"text": word, "scroll": True})
                continue

            # Try to add word to current page
            candidate = word if not current_page else f"{current_page} {word}"
            if len(candidate) <= max_chars:
                current_page = candidate
            else:
                # Current page is full, save it and start new
                if current_page:
                    pages.append({"text": current_page.strip(), "scroll": False})
                current_page = word

        # Don't forget the last page
        if current_page:
            pages.append({"text": current_page.strip(), "scroll": False})

        # If no pages, nothing to display
        if not pages:
            return

        # If only one page and it doesn't need scrolling, send directly
        if len(pages) == 1 and not pages[0]["scroll"]:
            img, error = sprite_service.render_text_fixed(
                pages[0]["text"], font_name, self.bg_color
            )
            if not error and img:
                path = save_temp_image(img, 'ipixel_text_sprite.png')
                self.device.send_image(path, resize_method='crop', save_slot=0)
            return

        # Multiple pages or scrolling needed - start page cycle
        self._start_sprite_page_cycle(pages, font_name, sprite_service)

    def _start_sprite_page_cycle(self, pages: list, font_name: str, sprite_service) -> None:
        """Cycle through pages of sprite text."""
        from ..utils.image_utils import save_temp_image

        page_index = 0
        delay_seconds = getattr(self, 'static_delay_var', None)
        delay_ms = (delay_seconds.get() if delay_seconds else 2) * 1000

        self.state.sprite_scroll_running = True

        def show_page():
            nonlocal page_index

            if not self.state.sprite_scroll_running:
                return

            if page_index >= len(pages):
                page_index = 0

            page = pages[page_index]

            if page["scroll"]:
                # This page needs scrolling
                img, error = sprite_service.render_text_line(
                    page["text"], font_name, self.bg_color
                )
                if not error and img:
                    self._scroll_single_page(img, pages, page_index, font_name, sprite_service, delay_ms)
                return
            else:
                # Static page
                img, error = sprite_service.render_text_fixed(
                    page["text"], font_name, self.bg_color
                )
                if not error and img:
                    path = save_temp_image(img, 'ipixel_text_sprite.png')
                    self.device.send_image(path, resize_method='crop', save_slot=0)

            page_index += 1

            if self.state.sprite_scroll_running:
                self.timers.schedule(TimerNames.TEXT_STATIC_CYCLE, delay_ms, show_page)

        show_page()

    def _scroll_single_page(self, img, pages: list, current_index: int, font_name: str, sprite_service, delay_ms: int) -> None:
        """Scroll a single long word, then continue to next page."""
        from ..utils.image_utils import save_temp_image
        from PIL import Image

        # Add padding
        padded = Image.new(img.mode, (img.width + 8, img.height), self.bg_color)
        padded.paste(img, (0, 0))
        img = padded

        if img.width <= 64:
            # Fits, just show it then move to next page
            if img.height != 16:
                img = img.resize((64, 16), Image.NEAREST)
            path = save_temp_image(img, 'ipixel_sprite_scroll.png')
            self.device.send_image(path, resize_method='crop', save_slot=0)
            # Schedule next page
            if self.state.sprite_scroll_running:
                self.timers.schedule(
                    TimerNames.TEXT_STATIC_CYCLE, delay_ms,
                    lambda: self._continue_page_cycle(pages, current_index + 1, font_name, sprite_service, delay_ms)
                )
            return

        # Scroll through the word
        max_offset = img.width - 64
        offset = 0
        speed = self.speed_var.get()
        interval = max(20, 220 - speed * 2)

        def scroll_tick():
            nonlocal offset

            if not self.state.sprite_scroll_running:
                return

            crop = img.crop((offset, 0, offset + 64, img.height))
            if img.height != 16:
                crop = crop.resize((64, 16), Image.NEAREST)

            path = save_temp_image(crop, 'ipixel_sprite_scroll.png')
            self.device.send_image(path, resize_method='crop', save_slot=0)

            offset += 1

            if offset > max_offset:
                # Done scrolling this word, move to next page
                if self.state.sprite_scroll_running:
                    self.timers.schedule(
                        TimerNames.TEXT_STATIC_CYCLE, delay_ms,
                        lambda: self._continue_page_cycle(pages, current_index + 1, font_name, sprite_service, delay_ms)
                    )
            elif self.state.sprite_scroll_running:
                self.timers.schedule(TimerNames.SPRITE_SCROLL, interval, scroll_tick)

        scroll_tick()

    def _continue_page_cycle(self, pages: list, page_index: int, font_name: str, sprite_service, delay_ms: int) -> None:
        """Continue the page cycle from a specific index."""
        from ..utils.image_utils import save_temp_image

        if not self.state.sprite_scroll_running:
            return

        if page_index >= len(pages):
            page_index = 0

        page = pages[page_index]

        if page["scroll"]:
            img, error = sprite_service.render_text_line(
                page["text"], font_name, self.bg_color
            )
            if not error and img:
                self._scroll_single_page(img, pages, page_index, font_name, sprite_service, delay_ms)
        else:
            img, error = sprite_service.render_text_fixed(
                page["text"], font_name, self.bg_color
            )
            if not error and img:
                path = save_temp_image(img, 'ipixel_text_sprite.png')
                self.device.send_image(path, resize_method='crop', save_slot=0)

            if self.state.sprite_scroll_running:
                self.timers.schedule(
                    TimerNames.TEXT_STATIC_CYCLE, delay_ms,
                    lambda idx=page_index + 1: self._continue_page_cycle(pages, idx, font_name, sprite_service, delay_ms)
                )

    def _start_sprite_scroll(self, img, reverse: bool = False) -> None:
        """Start scrolling sprite text animation."""
        from ..utils.image_utils import save_temp_image
        from PIL import Image

        # Add padding
        padded = Image.new(img.mode, (img.width + 8, img.height), self.bg_color)
        padded.paste(img, (0 if not reverse else 8, 0))
        img = padded

        if img.width <= 64:
            # Fits on screen, just send
            if img.height != 16:
                img = img.resize((64, 16), Image.NEAREST)
            path = save_temp_image(img, 'ipixel_sprite_scroll.png')
            self.device.send_image(path, resize_method='crop', save_slot=0)
            return

        # Setup scroll animation
        max_offset = img.width - 64
        offset = max_offset if reverse else 0
        step = -1 if reverse else 1
        speed = self.speed_var.get()
        interval = max(20, 220 - speed * 2)

        self.state.sprite_scroll_running = True

        def tick():
            nonlocal offset

            if not self.state.sprite_scroll_running:
                return

            # Crop visible portion
            crop = img.crop((offset, 0, offset + 64, img.height))
            if img.height != 16:
                crop = crop.resize((64, 16), Image.NEAREST)

            path = save_temp_image(crop, 'ipixel_sprite_scroll.png')
            self.device.send_image(path, resize_method='crop', save_slot=0)

            # Advance
            offset += step
            wrapped = False
            if offset > max_offset:
                offset = 0
                wrapped = True
            elif offset < 0:
                offset = max_offset
                wrapped = True

            if self.state.sprite_scroll_running:
                delay = 3000 if wrapped else interval
                self.timers.schedule(TimerNames.SPRITE_SCROLL, delay, tick)

        self.timers.schedule(TimerNames.SPRITE_SCROLL, interval, tick)

    def stop(self) -> None:
        """Stop any running operations."""
        self.state.sprite_scroll_running = False
        self.timers.cancel(TimerNames.SPRITE_SCROLL)
        self.timers.cancel(TimerNames.TEXT_STATIC_CYCLE)

    def _save_preset(self) -> None:
        """Save current settings as preset."""
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "Please enter some text.")
            return

        from ..ui.widgets.preset_dialog import PresetSaveDialog

        PresetSaveDialog(
            parent=self.root,
            preset_type="Text",
            default_name=text[:20],
            on_create=self.create_preset,
            on_complete=lambda p: self.config.add_preset(p)
        )

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Create a preset from current state."""
        return {
            'name': name,
            'type': self.feature_id,
            'text': self.text_input.get("1.0", tk.END).strip(),
            'text_color': self.text_color,
            'bg_color': self.bg_color,
            'animation': self.animation_var.get(),
            'speed': self.speed_var.get(),
            'rainbow': self.rainbow_var.get(),
            'text_use_sprite_font': self.use_sprite_var.get(),
            'text_sprite_font_name': self.sprite_font_var.get(),
            'text_static_delay_seconds': self.static_delay_var.get(),
        }

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute a saved preset."""
        # Restore settings
        self.text_input.delete("1.0", tk.END)
        self.text_input.insert("1.0", preset.get('text', ''))

        self.text_color = preset.get('text_color', '#FFFFFF')
        self.bg_color = preset.get('bg_color', '#000000')
        self.color_picker.text_color = self.text_color
        self.color_picker.bg_color = self.bg_color

        self.animation_var.set(preset.get('animation', 0))
        self.speed_var.set(preset.get('speed', 50))
        self.rainbow_var.set(preset.get('rainbow', 0))

        self.use_sprite_var.set(preset.get('text_use_sprite_font', False))
        self.sprite_font_var.set(preset.get('text_sprite_font_name', ''))
        self.static_delay_var.set(preset.get('text_static_delay_seconds', 2))

        return self.send_to_display()

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """Get preview text for preset."""
        text = preset.get('text', '')
        return text[:30] + "..." if len(text) > 30 else text

    def get_preset_details(self, preset: Dict[str, Any]) -> str:
        """Get detailed description for preset."""
        text = preset.get('text', 'Unknown')
        anim = preset.get('animation', 0)
        anim_names = {0: 'Static', 1: 'Scroll Left', 2: 'Scroll Right', 5: 'Blink'}
        return f"Text: {text[:50]}...\nAnimation: {anim_names.get(anim, 'Unknown')}"
