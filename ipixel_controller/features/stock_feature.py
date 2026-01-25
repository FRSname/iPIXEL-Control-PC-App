"""
Stock market display feature.

Displays live stock prices with auto-refresh support.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from .base import FeatureBase
from ..ui.widgets.color_picker import ColorPickerWidget
from ..ui.widgets.sprite_font_selector import SpriteFontSelector
from ..ui.widgets.auto_refresh_control import AutoRefreshControl
from ..core.timers import TimerNames
from ..services.stock_service import format_stock_display, get_stock_color


class StockFeature(FeatureBase):
    """
    Stock market display feature.

    Displays live stock prices with:
    - Multiple display formats
    - Auto-color based on price movement
    - Auto-refresh support
    - Sprite font rendering
    """

    feature_id = "stock"
    display_name = "Stock"
    tab_icon = "📈"

    FORMATS = [
        ("Price + Change %", "price_change"),
        ("Price Only", "price_only"),
        ("Ticker + Price", "ticker_price"),
        ("Full Info", "full"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_color = "#000000"
        self.current_data: Optional[Dict[str, Any]] = None

    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """Create the stock tab UI."""
        self.tab_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.tab_frame, text=self.tab_title)

        # Info
        info = self._create_info_label(
            self.tab_frame,
            "Display live stock prices. No API key required!"
        )
        info.pack(anchor=tk.W, pady=(0, 10))

        # Ticker input
        ticker_frame = ttk.LabelFrame(self.tab_frame, text="Stock Ticker", padding="10")
        ticker_frame.pack(fill=tk.X, pady=(0, 10))

        input_row = ttk.Frame(ticker_frame)
        input_row.pack(fill=tk.X)

        ttk.Label(input_row, text="Symbol:").pack(side=tk.LEFT)
        self.ticker_var = tk.StringVar(value="AAPL")
        ttk.Entry(
            input_row,
            textvariable=self.ticker_var,
            width=15
        ).pack(side=tk.LEFT, padx=(5, 10))

        self.fetch_button = ttk.Button(
            input_row,
            text="Fetch Data",
            command=self._fetch_data
        )
        self.fetch_button.pack(side=tk.LEFT)

        # Status
        self.status_var = tk.StringVar(value="Enter a ticker and click Fetch")
        ttk.Label(
            ticker_frame,
            textvariable=self.status_var,
            foreground="gray"
        ).pack(anchor=tk.W, pady=(10, 0))

        # Display options
        options_frame = ttk.LabelFrame(self.tab_frame, text="Display Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        # Format
        format_row = ttk.Frame(options_frame)
        format_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(format_row, text="Format:").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value="price_change")
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

        self.bg_picker = ColorPickerWidget(
            color_row,
            label="Background:",
            initial_color=self.bg_color,
            on_change=lambda c: setattr(self, 'bg_color', c)
        )
        self.bg_picker.pack(side=tk.LEFT, padx=(0, 20))

        self.auto_color_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            color_row,
            text="Auto-color (green/red)",
            variable=self.auto_color_var
        ).pack(side=tk.LEFT)

        # Sprite font
        self.use_sprite_var = tk.BooleanVar(
            value=self.state.settings.get('stock_use_sprite_font', True)
        )
        self.sprite_font_var = tk.StringVar(
            value=self.state.settings.get('stock_sprite_font_name', '')
        )

        self.sprite_selector = SpriteFontSelector(
            options_frame,
            font_names=self.config.get_sprite_font_names(),
            use_sprite_var=self.use_sprite_var,
            font_name_var=self.sprite_font_var
        )
        self.sprite_selector.pack(anchor=tk.W, pady=(0, 10))

        # Static delay for sprite pagination
        delay_frame = ttk.Frame(options_frame)
        delay_frame.pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(delay_frame, text="Static display delay:").pack(side=tk.LEFT)
        self.static_delay_var = tk.IntVar(
            value=self.state.settings.get('stock_static_delay_seconds', 2)
        )
        ttk.Spinbox(
            delay_frame,
            from_=1,
            to=10,
            textvariable=self.static_delay_var,
            width=5
        ).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(delay_frame, text="seconds").pack(side=tk.LEFT, padx=(5, 0))

        # Auto-refresh
        self.refresh_enabled_var = tk.BooleanVar(value=False)
        self.refresh_interval_var = tk.IntVar(value=60)

        self.refresh_control = AutoRefreshControl(
            options_frame,
            enabled_var=self.refresh_enabled_var,
            interval_var=self.refresh_interval_var,
            min_interval=30,
            max_interval=300
        )
        self.refresh_control.pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(self.tab_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.send_button = self._create_send_button(button_frame, "Send to Display")
        self.send_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Stop Refresh",
            command=self.stop
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Save as Preset",
            command=self._save_preset
        ).pack(side=tk.LEFT)

        return self.tab_frame

    def _fetch_data(self) -> None:
        """Fetch stock data."""
        ticker = self.ticker_var.get().strip().upper()
        if not ticker:
            messagebox.showwarning("No Ticker", "Please enter a stock ticker.")
            return

        self.status_var.set(f"Fetching {ticker}...")
        self.fetch_button.config(state=tk.DISABLED)

        # Get stock service
        stock_service = self.services.get('stock')
        if not stock_service:
            # Create one if not available
            from ..services.stock_service import StockService
            stock_service = StockService(
                self.root,
                self._on_data_fetched,
                self._on_fetch_error
            )
            self.services['stock'] = stock_service
        else:
            stock_service._on_success = self._on_data_fetched
            stock_service._on_error = self._on_fetch_error

        stock_service.fetch(ticker=ticker)

    def _on_data_fetched(self, data: Dict[str, Any]) -> None:
        """Handle fetched data."""
        self.current_data = data
        self.fetch_button.config(state=tk.NORMAL)

        price = data.get('price', 0)
        change = data.get('change', 0)
        change_pct = data.get('change_percent', 0)
        sign = '+' if change >= 0 else ''

        self.status_var.set(
            f"{data.get('ticker')}: ${price:.2f} ({sign}{change_pct:.2f}%)"
        )

    def _on_fetch_error(self, error: str) -> None:
        """Handle fetch error."""
        self.fetch_button.config(state=tk.NORMAL)
        self.status_var.set(f"Error: {error}")
        messagebox.showerror("Fetch Error", error)

    def send_to_display(self) -> bool:
        """Send stock data to display."""
        if not self.require_connection():
            return False

        if not self.current_data:
            messagebox.showwarning("No Data", "Please fetch stock data first.")
            return False

        self.stop_other_features()
        self.set_active()

        # Format display text
        display_text = format_stock_display(
            self.current_data,
            self.format_var.get()
        )

        # Determine color
        if self.auto_color_var.get():
            text_color = get_stock_color(self.current_data)
        else:
            text_color = "#FFFFFF"

        # Send to display
        if self.use_sprite_var.get():
            self._send_sprite_text(display_text, text_color)
        else:
            self.device.send_text(
                display_text,
                char_height=16,
                color=text_color,
                bg_color=self.bg_color,
                animation=0,
                speed=50
            )

        # Setup auto-refresh
        if self.refresh_enabled_var.get():
            self._schedule_refresh()

        return True

    def _send_sprite_text(self, text: str, color: str) -> None:
        """Send text using sprite font with pagination."""
        sprite_service = self.services.get('sprite_font')
        if not sprite_service:
            # Fallback
            self.device.send_text(text, color=color, bg_color=self.bg_color)
            return

        font_name = self.sprite_font_var.get()
        font = self.config.get_sprite_font_by_name(font_name)

        if not font:
            self.device.send_text(text, color=color, bg_color=self.bg_color)
            return

        self._send_sprite_text_paginated(text, font_name, font, sprite_service)

    def _send_sprite_text_paginated(self, text: str, font_name: str, font: dict, sprite_service) -> None:
        """Send sprite text with pagination for static display."""
        from PIL import Image
        from ..utils.image_utils import save_temp_image

        # Calculate max characters that fit in 64 pixels
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
                path = save_temp_image(img, 'ipixel_stock.png')
                self.device.send_image(path, resize_method='crop', save_slot=0)
            return

        # Multiple pages or scrolling needed - start page cycle
        self._start_sprite_page_cycle(pages, font_name, sprite_service)

    def _start_sprite_page_cycle(self, pages: list, font_name: str, sprite_service) -> None:
        """Cycle through pages of sprite text."""
        from ..utils.image_utils import save_temp_image

        page_index = 0
        delay_ms = self.static_delay_var.get() * 1000

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
                    path = save_temp_image(img, 'ipixel_stock.png')
                    self.device.send_image(path, resize_method='crop', save_slot=0)

            page_index += 1

            if self.state.sprite_scroll_running:
                self.timers.schedule(TimerNames.STOCK_STATIC_CYCLE, delay_ms, show_page)

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
            path = save_temp_image(img, 'ipixel_stock_scroll.png')
            self.device.send_image(path, resize_method='crop', save_slot=0)
            # Schedule next page
            if self.state.sprite_scroll_running:
                self.timers.schedule(
                    TimerNames.STOCK_STATIC_CYCLE, delay_ms,
                    lambda: self._continue_page_cycle(pages, current_index + 1, font_name, sprite_service, delay_ms)
                )
            return

        # Scroll through the word
        max_offset = img.width - 64
        offset = 0
        interval = 100  # Fixed scroll speed for stock

        def scroll_tick():
            nonlocal offset

            if not self.state.sprite_scroll_running:
                return

            crop = img.crop((offset, 0, offset + 64, img.height))
            if img.height != 16:
                crop = crop.resize((64, 16), Image.NEAREST)

            path = save_temp_image(crop, 'ipixel_stock_scroll.png')
            self.device.send_image(path, resize_method='crop', save_slot=0)

            offset += 1

            if offset > max_offset:
                # Done scrolling this word, move to next page
                if self.state.sprite_scroll_running:
                    self.timers.schedule(
                        TimerNames.STOCK_STATIC_CYCLE, delay_ms,
                        lambda: self._continue_page_cycle(pages, current_index + 1, font_name, sprite_service, delay_ms)
                    )
            elif self.state.sprite_scroll_running:
                self.timers.schedule(TimerNames.STOCK_REFRESH, interval, scroll_tick)

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
                path = save_temp_image(img, 'ipixel_stock.png')
                self.device.send_image(path, resize_method='crop', save_slot=0)

            if self.state.sprite_scroll_running:
                self.timers.schedule(
                    TimerNames.STOCK_STATIC_CYCLE, delay_ms,
                    lambda idx=page_index + 1: self._continue_page_cycle(pages, idx, font_name, sprite_service, delay_ms)
                )

    def _schedule_refresh(self) -> None:
        """Schedule auto-refresh."""
        def refresh():
            self._fetch_data()
            # Send after fetch completes
            self.root.after(2000, self.send_to_display)

        interval = self.refresh_interval_var.get() * 1000
        self.timers.schedule(TimerNames.STOCK_REFRESH, interval, refresh)

    def stop(self) -> None:
        """Stop auto-refresh and sprite scrolling."""
        self.state.sprite_scroll_running = False
        self.timers.cancel(TimerNames.STOCK_REFRESH)
        self.timers.cancel(TimerNames.STOCK_STATIC_CYCLE)

    def _save_preset(self) -> None:
        """Save as preset."""
        if not self.current_data:
            messagebox.showwarning("No Data", "Please fetch stock data first.")
            return

        from ..ui.widgets.preset_dialog import PresetSaveDialog

        ticker = self.current_data.get('ticker', 'Stock')
        PresetSaveDialog(
            parent=self.root,
            preset_type="Stock",
            default_name=f"Stock - {ticker}",
            on_create=self.create_preset,
            on_complete=lambda p: self.config.add_preset(p)
        )

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Create preset."""
        return {
            'name': name,
            'type': self.feature_id,
            'ticker': self.ticker_var.get(),
            'format': self.format_var.get(),
            'bg_color': self.bg_color,
            'auto_color': self.auto_color_var.get(),
            'auto_refresh': self.refresh_enabled_var.get(),
            'refresh_interval': self.refresh_interval_var.get(),
            'stock_use_sprite_font': self.use_sprite_var.get(),
            'stock_sprite_font_name': self.sprite_font_var.get(),
            'stock_static_delay_seconds': self.static_delay_var.get(),
        }

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute preset."""
        self.ticker_var.set(preset.get('ticker', 'AAPL'))
        self.format_var.set(preset.get('format', 'price_change'))
        self.bg_color = preset.get('bg_color', '#000000')
        self.bg_picker.set_color(self.bg_color)
        self.auto_color_var.set(preset.get('auto_color', True))
        self.refresh_enabled_var.set(preset.get('auto_refresh', False))
        self.refresh_interval_var.set(preset.get('refresh_interval', 60))
        self.use_sprite_var.set(preset.get('stock_use_sprite_font', True))
        self.sprite_font_var.set(preset.get('stock_sprite_font_name', ''))
        self.static_delay_var.set(preset.get('stock_static_delay_seconds', 2))

        # Fetch and send
        self._fetch_data()
        self.root.after(2000, self.send_to_display)
        return True

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """Get preset preview."""
        return preset.get('ticker', 'Stock')
