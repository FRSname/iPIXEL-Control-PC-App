#!/usr/bin/env python3
"""
iPixel LED Panel Controller e
A desktop application to control iPixel Color LED matrix displays via Bluetooth
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import asyncio
import threading
from PIL import Image, ImageTk, ImageDraw, ImageFont
import requests
import urllib.parse
import os
import sys
import tempfile
import math
import json

try:
    from pypixelcolor import Client
    from bleak import BleakScanner
except ImportError:
    print("Required libraries not installed. Please run: pip install pypixelcolor bleak pillow")
    sys.exit(1)


class iPixelController:
    def __init__(self, root):
        self.root = root
        self.root.title("iPixel LED Panel Controller")
        self.root.geometry("800x1000")
        self.root.minsize(700, 800)
        
        self.client = None
        self.device_address = None
        self.is_connected = False
        self.loop = None
        
        # Initialize presets
        self.presets_file = "ipixel_presets.json"
        self.settings_file = "ipixel_settings.json"
        self.secrets_file = "ipixel_secrets.json"
        self.presets = []
        self.thumbnail_cache = {}  # Cache for PhotoImage objects
        self.load_presets()
        self.settings = self.load_settings()
        self.secrets = self.load_secrets()
        default_text_sprite_path = os.path.join("Gallery", "Sprites", "TextSprite.png")
        default_clock_sprite_path = os.path.join("Gallery", "Sprites", "SmallerClocksSprite-transp.png")
        default_youtube_logo_path = os.path.join("Gallery", "Sprites", "YT-btn.png")
        default_weather_dir = os.path.join("Gallery", "Weather")
        self.settings.setdefault('clock_use_time_sprite', False)
        self.settings.setdefault('text_use_sprite_font', False)
        self.settings.setdefault('text_sprite_font_name', '')
        self.settings.setdefault('countdown_use_sprite_font', False)
        self.settings.setdefault('countdown_sprite_font_name', '')
        self.settings.setdefault('clock_time_sprite_font_name', '')
        self.settings.setdefault('stock_use_sprite_font', True)
        self.settings.setdefault('stock_sprite_font_name', '')
        self.settings.setdefault('youtube_use_sprite_font', True)
        self.settings.setdefault('youtube_sprite_font_name', '')
        self.settings.setdefault('youtube_show_logo', True)
        self.settings.setdefault('youtube_logo_path', default_youtube_logo_path)
        self.settings.setdefault('youtube_logo_delay_seconds', 2)
        self.settings.setdefault('sprite_fonts', [])
        self.settings.setdefault('stock_static_delay_seconds', 2)
        self.settings.setdefault('text_static_delay_seconds', 2)
        self.settings.setdefault('countdown_static_delay_seconds', 2)
        if not self.settings.get('weather_temp_image_dir'):
            self.settings['weather_temp_image_dir'] = default_weather_dir

        # Migrate legacy sprite settings into library if needed
        if not self.settings.get('sprite_fonts'):
            legacy_path = self.settings.get('text_sprite_path', '').strip()
            legacy_order = self.settings.get('text_sprite_order', '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/ ')
            legacy_cols = self.settings.get('text_sprite_cols', 11)
            if legacy_path:
                self.settings['sprite_fonts'] = [{
                    'name': 'Default',
                    'path': legacy_path,
                    'order': legacy_order,
                    'cols': int(legacy_cols or 1)
                }]
                if not self.settings.get('text_sprite_font_name'):
                    self.settings['text_sprite_font_name'] = 'Default'
                self.save_settings()
            else:
                self.settings['sprite_fonts'] = [
                    {
                        'name': 'Text Default',
                        'path': default_text_sprite_path,
                        'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$% ',
                        'cols': 73
                    },
                    {
                        'name': 'Clock Default',
                        'path': default_clock_sprite_path,
                        'order': '0123456789:',
                        'cols': 11
                    }
                ]
                if not self.settings.get('text_sprite_font_name'):
                    self.settings['text_sprite_font_name'] = 'Text Default'
                if not self.settings.get('countdown_sprite_font_name'):
                    self.settings['countdown_sprite_font_name'] = 'Text Default'
                if not self.settings.get('stock_sprite_font_name'):
                    self.settings['stock_sprite_font_name'] = 'Text Default'
                if not self.settings.get('youtube_sprite_font_name'):
                    self.settings['youtube_sprite_font_name'] = 'Text Default'
                if not self.settings.get('clock_time_sprite_font_name'):
                    self.settings['clock_time_sprite_font_name'] = 'Clock Default'
                self.save_settings()

        self._ensure_default_sprite_fonts()
        
        # Teams status monitoring
        self.teams_monitoring = False
        self.teams_access_token = None
        self.teams_refresh_token = None
        self.teams_last_status = None
        self.teams_last_error = None
        self.teams_timer = None
        self.teams_debug_info = None
        self.stock_refresh_timer = None
        self.stock_static_timer = None
        self.sprite_scroll_timer = None
        self.sprite_scroll_running = False
        self.text_static_timer = None
        self.countdown_static_timer = None
        
        # Setup UI
        self.setup_ui()
        
        # Start async event loop in separate thread
        self.start_event_loop()
        
        # Auto-connect to last device if enabled
        if self.settings.get('auto_connect', True):
            self.root.after(1000, self.auto_connect_to_last_device)
            # Restore last state after connection
            if self.settings.get('restore_last_state', True):
                self.root.after(3000, self.restore_last_state)
        
    def setup_ui(self):
        """Create the user interface"""
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Connection Section
        connection_frame = ttk.LabelFrame(main_frame, text="Connection", padding="10")
        connection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        connection_frame.columnconfigure(1, weight=1)
        
        ttk.Label(connection_frame, text="Device:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(connection_frame, textvariable=self.device_var, state="readonly")
        self.device_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.scan_btn = ttk.Button(connection_frame, text="Scan", command=self.scan_devices)
        self.scan_btn.grid(row=0, column=2, padx=(0, 5))
        
        self.connect_btn = ttk.Button(connection_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3)
        
        self.status_label = ttk.Label(connection_frame, text="Not connected", foreground="red")
        self.status_label.grid(row=1, column=0, columnspan=4, pady=(5, 0))
        
        # Notebook for different control modes (keeping ttk.Notebook for simplicity)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10), padx=10)
        main_frame.rowconfigure(1, weight=1)
        
        # Create tab contents
        self.create_control_board_tab()
        self.create_text_tab()
        self.create_image_tab()
        self.create_clock_tab()
        self.create_stock_tab()
        self.create_youtube_tab()
        self.create_weather_tab()
        self.create_animations_tab()
        self.create_teams_status_tab()
        self.create_settings_tab()
        
    def create_control_board_tab(self):
        """Create the control board with preset buttons"""
        control_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(control_frame, text="Control Board")
        
        control_frame.columnconfigure(0, weight=1)
        
        # Info
        info_label = ttk.Label(control_frame, 
                              text="Quick access to saved presets. Create presets in other tabs and save them here.",
                              font=('TkDefaultFont', 9, 'italic'), wraplength=750)
        info_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Preset buttons area
        self.presets_frame = ttk.LabelFrame(control_frame, text="Saved Presets", padding="10")
        self.presets_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        control_frame.rowconfigure(1, weight=1)
        
        # Container for preset buttons (with scrollbar)
        canvas_frame = ttk.Frame(self.presets_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.presets_canvas = tk.Canvas(canvas_frame, height=400)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.presets_canvas.yview)
        self.presets_scrollable_frame = ttk.Frame(self.presets_canvas)
        
        self.presets_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.presets_canvas.configure(scrollregion=self.presets_canvas.bbox("all"))
        )
        
        self.presets_canvas.create_window((0, 0), window=self.presets_scrollable_frame, anchor="nw")
        self.presets_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.presets_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if event.num == 4:
                self.presets_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.presets_canvas.yview_scroll(1, "units")
            else:
                self.presets_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(_event=None):
            self.presets_canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.presets_canvas.bind_all("<Button-4>", _on_mousewheel)
            self.presets_canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_mousewheel(_event=None):
            self.presets_canvas.unbind_all("<MouseWheel>")
            self.presets_canvas.unbind_all("<Button-4>")
            self.presets_canvas.unbind_all("<Button-5>")

        self.presets_canvas.bind("<Enter>", _bind_mousewheel)
        self.presets_canvas.bind("<Leave>", _unbind_mousewheel)
        self.presets_scrollable_frame.bind("<Enter>", _bind_mousewheel)
        self.presets_scrollable_frame.bind("<Leave>", _unbind_mousewheel)
        
        # Playlist section
        playlist_frame = ttk.LabelFrame(control_frame, text="🎵 Playlist - Auto Switch Presets", padding="10")
        playlist_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 10))
        
        # Playlist controls
        playlist_control_frame = ttk.Frame(playlist_frame)
        playlist_control_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(playlist_control_frame, text="▶️ Play", 
                  command=self.play_playlist, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(playlist_control_frame, text="⏸️ Pause", 
                  command=self.pause_playlist, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(playlist_control_frame, text="⏹️ Stop", 
                  command=self.stop_playlist, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(playlist_control_frame, text="✏️ Edit Playlist", 
                  command=self.edit_playlist, width=15).pack(side=tk.LEFT, padx=(10, 0))
        
        # Playlist management buttons (second row)
        playlist_manage_frame = ttk.Frame(playlist_frame)
        playlist_manage_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(playlist_manage_frame, text="💾 Save Playlist As...", 
                  command=self.save_playlist, width=18).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(playlist_manage_frame, text="📂 Load Playlist", 
                  command=self.load_playlist_dialog, width=18).pack(side=tk.LEFT, padx=(0, 5))
        
        # Current playlist name
        self.current_playlist_name_var = tk.StringVar(value="(Unsaved playlist)")
        ttk.Label(playlist_manage_frame, textvariable=self.current_playlist_name_var, 
                 font=('TkDefaultFont', 8, 'italic'), foreground='gray').pack(side=tk.LEFT, padx=(10, 0))
        
        # Playlist status
        self.playlist_status_var = tk.StringVar(value="Playlist: Not running")
        ttk.Label(playlist_control_frame, textvariable=self.playlist_status_var, 
                 font=('TkDefaultFont', 9, 'italic')).pack(side=tk.LEFT, padx=(20, 0))
        
        # Action buttons
        action_frame = ttk.Frame(control_frame)
        action_frame.grid(row=3, column=0, pady=(10, 0))
        
        ttk.Button(action_frame, text="➕ Save Current as Preset", 
                  command=self.save_current_preset).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="📁 Import Presets", 
                  command=self.import_presets).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="💾 Export Presets", 
                  command=self.export_presets).pack(side=tk.LEFT)
        
        # Initialize playlist state
        self.playlist = []
        self.current_playlist_file = None  # Track current playlist file
        self.playlist_running = False
        self.playlist_paused = False
        self.playlist_index = 0
        self.playlist_timer = None
        
        # Render preset buttons
        self.refresh_preset_buttons()
        
    def create_text_tab(self):
        """Create the text control tab"""
        text_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(text_frame, text="Text")
        
        text_frame.columnconfigure(1, weight=1)
        text_frame.rowconfigure(1, weight=1)
        
        # Text input
        ttk.Label(text_frame, text="Text:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.text_input = tk.Text(text_frame, height=5, width=40)
        self.text_input.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Text color
        ttk.Label(text_frame, text="Text Color:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        color_frame = ttk.Frame(text_frame)
        color_frame.grid(row=2, column=1, sticky=tk.W, pady=(0, 5))
        
        self.text_color = "#FFFFFF"
        self.text_color_canvas = tk.Canvas(color_frame, width=30, height=20, bg=self.text_color, relief=tk.SUNKEN)
        self.text_color_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(color_frame, text="Choose", command=self.choose_text_color).pack(side=tk.LEFT)
        
        # Background color
        ttk.Label(text_frame, text="Background:").grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        
        bg_frame = ttk.Frame(text_frame)
        bg_frame.grid(row=3, column=1, sticky=tk.W, pady=(0, 10))
        
        self.bg_color = "#FFFFFF"
        self.bg_color_canvas = tk.Canvas(bg_frame, width=30, height=20, bg=self.bg_color, relief=tk.SUNKEN)
        self.bg_color_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(bg_frame, text="Choose", command=self.choose_bg_color).pack(side=tk.LEFT)
        
        # Animation
        ttk.Label(text_frame, text="Animation:").grid(row=4, column=0, sticky=tk.W, pady=(0, 5))
        
        self.animation_var = tk.IntVar(value=0)
        animation_frame = ttk.Frame(text_frame)
        animation_frame.grid(row=4, column=1, sticky=tk.W, pady=(0, 5))
        
        animations = [
            ("Static", 0),
            ("Scroll Left", 1),
            ("Scroll Right", 2),
            ("Flash", 5),
        ]
        for text, value in animations:
            ttk.Radiobutton(animation_frame, text=text, variable=self.animation_var, value=value).pack(side=tk.LEFT, padx=(0, 5))
        
        # Speed (for animations)
        ttk.Label(text_frame, text="Speed:").grid(row=5, column=0, sticky=tk.W, pady=(0, 5))
        
        self.speed_var = tk.IntVar(value=50)
        speed_frame = ttk.Frame(text_frame)
        speed_frame.grid(row=5, column=1, sticky=tk.W, pady=(0, 5))
        
        ttk.Scale(speed_frame, from_=10, to=100, variable=self.speed_var, orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(speed_frame, textvariable=self.speed_var).pack(side=tk.LEFT)
        
        # Rainbow mode (animated color effects)
        ttk.Label(text_frame, text="Rainbow Effect:").grid(row=6, column=0, sticky=tk.W, pady=(0, 5))
        
        self.rainbow_var = tk.IntVar(value=0)
        rainbow_frame = ttk.Frame(text_frame)
        rainbow_frame.grid(row=6, column=1, sticky=tk.W, pady=(0, 5))
        
        rainbow_row1 = ttk.Frame(rainbow_frame)
        rainbow_row1.pack(anchor=tk.W)
        rainbow_row2 = ttk.Frame(rainbow_frame)
        rainbow_row2.pack(anchor=tk.W)
        
        rainbow_modes = [
            ("None", 0),
            ("Mode 1", 1),
            ("Mode 2", 2),
            ("Mode 3", 3),
            ("Mode 4", 4),
            ("Mode 5", 5),
            ("Mode 6", 6),
            ("Mode 7", 7),
            ("Mode 8", 8),
            ("Mode 9", 9),
        ]
        for i, (text, value) in enumerate(rainbow_modes):
            parent = rainbow_row1 if i < 5 else rainbow_row2
            ttk.Radiobutton(parent, text=text, variable=self.rainbow_var, value=value).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(text_frame, text="(Different rainbow modes create various color effects)", 
                 font=('TkDefaultFont', 8, 'italic')).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        # Sprite font (custom text)
        sprite_frame = ttk.LabelFrame(text_frame, text="Sprite Font", padding="8")
        sprite_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        sprite_frame.columnconfigure(1, weight=1)

        self.text_use_sprite_var = tk.BooleanVar(value=self.settings.get('text_use_sprite_font', False))
        ttk.Checkbutton(
            sprite_frame,
            text="Use sprite font",
            variable=self.text_use_sprite_var,
            command=self.update_text_sprite_settings
        ).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(sprite_frame, text="Font:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.text_sprite_font_var = tk.StringVar(value=self.settings.get('text_sprite_font_name', ''))
        self.text_sprite_font_combo = ttk.Combobox(sprite_frame, textvariable=self.text_sprite_font_var, state="readonly")
        self.text_sprite_font_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        self.text_sprite_font_combo.bind('<<ComboboxSelected>>', lambda e: self.update_text_sprite_settings())

        ttk.Label(sprite_frame, text="Note: Sprite font ignores animation/rainbow.", foreground="gray").grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(2, 0)
        )

        ttk.Label(text_frame, text="Static delay (s):").grid(row=10, column=0, sticky=tk.W, pady=(0, 5))
        self.text_static_delay_var = tk.IntVar(value=self.settings.get('text_static_delay_seconds', 2))
        ttk.Spinbox(text_frame, from_=1, to=30, textvariable=self.text_static_delay_var, width=5,
                    command=self.update_text_sprite_settings).grid(row=10, column=1, sticky=tk.W, pady=(0, 5))
        
        # Send button
        self.send_text_btn = ttk.Button(text_frame, text="Send Text", command=self.send_text, state=tk.DISABLED)
        self.send_text_btn.grid(row=11, column=0, columnspan=2, pady=(10, 0))
        
    def create_image_tab(self):
        """Create the image control tab"""
        image_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(image_frame, text="Image")
        
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(1, weight=1)
        
        # Resolution info
        info_frame = ttk.LabelFrame(image_frame, text="Display Resolution & Animation Support", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        info_text = "Your Display: 16x64 pixels (rectangular)\n\n" \
                   "Supported Formats:\n" \
                   "• Static Images: PNG, JPG, BMP (64x16 pixels recommended)\n" \
                   "• Animated: GIF files (will play animation loop)\n\n" \
                   "Create images at 64x16 pixels for best results.\n" \
                   "GIF animations will loop continuously on the display."
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack()
        
        # Image preview
        self.image_preview_frame = ttk.LabelFrame(image_frame, text="Preview", padding="10")
        self.image_preview_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.image_preview_label = ttk.Label(self.image_preview_frame, text="No image loaded")
        self.image_preview_label.pack()
        
        self.image_path = None
        
        # Buttons
        btn_frame = ttk.Frame(image_frame)
        btn_frame.grid(row=2, column=0, pady=(0, 10))
        
        ttk.Button(btn_frame, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=(0, 5))
        self.send_image_btn = ttk.Button(btn_frame, text="Send Image", command=self.send_image, state=tk.DISABLED)
        self.send_image_btn.pack(side=tk.LEFT)
        
    def create_clock_tab(self):
        """Create the clock control tab"""
        clock_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(clock_frame, text="Clock")
        
        ttk.Label(clock_frame, text="Display current time on the LED panel", 
                 font=('TkDefaultFont', 10, 'bold')).pack(pady=(0, 10))
        
        # Clock mode selection
        self.clock_mode_var = tk.StringVar(value="builtin")
        
        mode_frame = ttk.LabelFrame(clock_frame, text="Clock Mode", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Radiobutton(mode_frame, text="Built-in Hardware Clock (static styles)", 
                       variable=self.clock_mode_var, value="builtin",
                       command=self.update_clock_options).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Custom Design (live updating)", 
                       variable=self.clock_mode_var, value="custom",
                       command=self.update_clock_options).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Countdown Timer (count to event)", 
                       variable=self.clock_mode_var, value="countdown",
                       command=self.update_clock_options).pack(anchor=tk.W)
        
        # Built-in clock styles
        self.builtin_frame = ttk.LabelFrame(clock_frame, text="Built-in Clock Styles", padding="10")
        self.builtin_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.builtin_frame, text="Select style:", 
                 font=('TkDefaultFont', 9, 'italic')).pack(anchor=tk.W, pady=(0, 5))
        
        self.clock_style_var = tk.IntVar(value=0)
        styles = ["Style 0", "Style 1", "Style 2", "Style 3", "Style 4", 
                 "Style 5", "Style 6", "Style 7", "Style 8"]
        
        style_grid = ttk.Frame(self.builtin_frame)
        style_grid.pack(fill=tk.X)
        
        for i, style in enumerate(styles):
            row = i // 3
            col = i % 3
            ttk.Radiobutton(style_grid, text=style, variable=self.clock_style_var, 
                          value=i).grid(row=row, column=col, sticky=tk.W, padx=10, pady=2)
        
        # Custom clock designs
        self.custom_frame = ttk.LabelFrame(clock_frame, text="Custom Clock Design", padding="10")
        self.custom_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.custom_frame, text="Time Format:", 
                 font=('TkDefaultFont', 9, 'italic')).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.time_format_var = tk.StringVar(value="%H:%M:%S")
        
        formats = [
            ("24h with seconds (HH:MM:SS)", "%H:%M:%S"),
            ("24h without seconds (HH:MM)", "%H:%M"),
            ("12h with seconds (HH:MM:SS AM/PM)", "%I:%M:%S %p"),
            ("12h without seconds (HH:MM AM/PM)", "%I:%M %p"),
            ("Time & Date (HH:MM DD/MM)", "%H:%M %d/%m"),
            ("Minimal (HH:MM)", "%H:%M"),
            ("With day (Mon HH:MM)", "%a %H:%M"),
        ]
        
        for i, (label, fmt) in enumerate(formats):
            ttk.Radiobutton(self.custom_frame, text=label, variable=self.time_format_var, 
                          value=fmt).grid(row=i+1, column=0, sticky=tk.W, pady=2)
        
        # Custom clock color settings
        color_frame = ttk.Frame(self.custom_frame)
        color_frame.grid(row=len(formats)+1, column=0, sticky=tk.W, pady=(10, 5))
        
        ttk.Label(color_frame, text="Text Color:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.clock_color = "#00ffff"  # Cyan default (lowercase)
        self.clock_color_canvas = tk.Canvas(color_frame, width=30, height=20, 
                                            bg=self.clock_color, relief=tk.SUNKEN)
        self.clock_color_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(color_frame, text="Choose", command=self.choose_clock_color).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Label(color_frame, text="Background:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.clock_bg_color = "#FFFFFF"
        self.clock_bg_color_canvas = tk.Canvas(color_frame, width=30, height=20, 
                                               bg=self.clock_bg_color, relief=tk.SUNKEN)
        self.clock_bg_color_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(color_frame, text="Choose", command=self.choose_clock_bg_color).pack(side=tk.LEFT)
        
        # Custom clock animation
        anim_frame = ttk.Frame(self.custom_frame)
        anim_frame.grid(row=len(formats)+2, column=0, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(anim_frame, text="Animation:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.clock_animation_var = tk.StringVar(value="static")
        clock_animations = ["Static", "Scroll Left", "Flash"]
        
        for anim in clock_animations:
            ttk.Radiobutton(anim_frame, text=anim, variable=self.clock_animation_var, 
                          value=anim.lower().replace(" ", "_")).pack(side=tk.LEFT, padx=5)
        
        # Update interval for custom clocks
        interval_frame = ttk.Frame(self.custom_frame)
        interval_frame.grid(row=len(formats)+3, column=0, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(interval_frame, text="Update every:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.clock_update_interval_var = tk.IntVar(value=1)
        ttk.Spinbox(interval_frame, from_=1, to=60, textvariable=self.clock_update_interval_var, 
                   width=5).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(interval_frame, text="second(s)").pack(side=tk.LEFT)

        # Sprite font for time glyphs
        sprite_frame = ttk.Frame(self.custom_frame)
        sprite_frame.grid(row=len(formats)+5, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        sprite_frame.columnconfigure(1, weight=1)

        self.clock_use_time_sprite_var = tk.BooleanVar(value=self.settings.get('clock_use_time_sprite', False))
        ttk.Checkbutton(
            sprite_frame,
            text="Use sprite font",
            variable=self.clock_use_time_sprite_var,
            command=self.update_clock_sprite_settings
        ).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(sprite_frame, text="Font:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.clock_sprite_font_var = tk.StringVar(value=self.settings.get('clock_time_sprite_font_name', ''))
        self.clock_sprite_font_combo = ttk.Combobox(sprite_frame, textvariable=self.clock_sprite_font_var, state="readonly")
        self.clock_sprite_font_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        self.clock_sprite_font_combo.bind('<<ComboboxSelected>>', lambda e: self.update_clock_sprite_settings())

        self.clock_image_status_var = tk.StringVar(value="Clock status will appear here")
        ttk.Label(sprite_frame, textvariable=self.clock_image_status_var, foreground="gray").grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(2, 0)
        )
        
        # Countdown timer frame
        self.countdown_frame = ttk.LabelFrame(clock_frame, text="⏱️ Countdown Timer", padding="10")
        self.countdown_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.countdown_frame, text="Count down to your event!", 
                 font=('TkDefaultFont', 9, 'italic')).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Event name
        ttk.Label(self.countdown_frame, text="Event Name:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.countdown_event_var = tk.StringVar(value="Event")
        ttk.Entry(self.countdown_frame, textvariable=self.countdown_event_var, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Target date and time
        ttk.Label(self.countdown_frame, text="Target Date:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        date_frame = ttk.Frame(self.countdown_frame)
        date_frame.grid(row=2, column=1, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(date_frame, text="Year:").pack(side=tk.LEFT, padx=(0, 5))
        self.countdown_year_var = tk.IntVar(value=2026)
        ttk.Spinbox(date_frame, from_=2026, to=2099, textvariable=self.countdown_year_var, width=6).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(date_frame, text="Month:").pack(side=tk.LEFT, padx=(0, 5))
        self.countdown_month_var = tk.IntVar(value=1)
        ttk.Spinbox(date_frame, from_=1, to=12, textvariable=self.countdown_month_var, width=4).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(date_frame, text="Day:").pack(side=tk.LEFT, padx=(0, 5))
        self.countdown_day_var = tk.IntVar(value=1)
        ttk.Spinbox(date_frame, from_=1, to=31, textvariable=self.countdown_day_var, width=4).pack(side=tk.LEFT)
        
        # Target time
        ttk.Label(self.countdown_frame, text="Target Time:").grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        
        time_frame = ttk.Frame(self.countdown_frame)
        time_frame.grid(row=3, column=1, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(time_frame, text="Hour:").pack(side=tk.LEFT, padx=(0, 5))
        self.countdown_hour_var = tk.IntVar(value=0)
        ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self.countdown_hour_var, width=4).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(time_frame, text="Minute:").pack(side=tk.LEFT, padx=(0, 5))
        self.countdown_minute_var = tk.IntVar(value=0)
        ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self.countdown_minute_var, width=4).pack(side=tk.LEFT)
        
        # Display format
        ttk.Label(self.countdown_frame, text="Display Format:").grid(row=4, column=0, sticky=tk.W, pady=(10, 5))
        
        self.countdown_format_var = tk.StringVar(value="days_hours_mins")
        
        format_options = [
            ("Days, Hours, Minutes (123d 5h 30m)", "days_hours_mins"),
            ("Days and Hours (123d 5h)", "days_hours"),
            ("Total Hours and Minutes (2965h 30m)", "hours_mins"),
            ("Days only (123 days)", "days_only"),
            ("With event name (Event: 123d 5h 30m)", "with_name"),
        ]
        
        for i, (label, value) in enumerate(format_options):
            ttk.Radiobutton(self.countdown_frame, text=label, variable=self.countdown_format_var, 
                          value=value).grid(row=5+i, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Countdown colors
        countdown_color_frame = ttk.Frame(self.countdown_frame)
        countdown_color_frame.grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))
        
        ttk.Label(countdown_color_frame, text="Text Color:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.countdown_color = "#00ff00"  # Green default
        self.countdown_color_canvas = tk.Canvas(countdown_color_frame, width=30, height=20, 
                                               bg=self.countdown_color, relief=tk.SUNKEN)
        self.countdown_color_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(countdown_color_frame, text="Choose", command=self.choose_countdown_color).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Label(countdown_color_frame, text="Background:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.countdown_bg_color = "#FFFFFF"
        self.countdown_bg_color_canvas = tk.Canvas(countdown_color_frame, width=30, height=20, 
                                                   bg=self.countdown_bg_color, relief=tk.SUNKEN)
        self.countdown_bg_color_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(countdown_color_frame, text="Choose", command=self.choose_countdown_bg_color).pack(side=tk.LEFT)

        # Countdown sprite font
        countdown_sprite_frame = ttk.Frame(self.countdown_frame)
        countdown_sprite_frame.grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        self.countdown_use_sprite_var = tk.BooleanVar(value=self.settings.get('countdown_use_sprite_font', False))
        ttk.Checkbutton(
            countdown_sprite_frame,
            text="Use sprite font",
            variable=self.countdown_use_sprite_var,
            command=self.update_countdown_sprite_settings
        ).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(countdown_sprite_frame, text="Font:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.countdown_sprite_font_var = tk.StringVar(value=self.settings.get('countdown_sprite_font_name', ''))
        self.countdown_sprite_font_combo = ttk.Combobox(countdown_sprite_frame, textvariable=self.countdown_sprite_font_var, state="readonly")
        self.countdown_sprite_font_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        self.countdown_sprite_font_combo.bind('<<ComboboxSelected>>', lambda e: self.update_countdown_sprite_settings())

        ttk.Label(self.countdown_frame, text="Static delay (s):").grid(row=12, column=0, sticky=tk.W, pady=(5, 0))
        self.countdown_static_delay_var = tk.IntVar(value=self.settings.get('countdown_static_delay_seconds', 2))
        ttk.Spinbox(self.countdown_frame, from_=1, to=60, textvariable=self.countdown_static_delay_var, width=5,
                command=self.update_countdown_sprite_settings).grid(row=12, column=1, sticky=tk.W, pady=(5, 0))
        
        # Countdown animation
        countdown_anim_frame = ttk.Frame(self.countdown_frame)
        countdown_anim_frame.grid(row=13, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(countdown_anim_frame, text="Animation:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.countdown_animation_var = tk.StringVar(value="static")
        
        for anim in ["Static", "Scroll Left", "Flash"]:
            ttk.Radiobutton(countdown_anim_frame, text=anim, variable=self.countdown_animation_var, 
                          value=anim.lower().replace(" ", "_")).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(countdown_anim_frame, text="Speed:").pack(side=tk.LEFT, padx=(15, 5))
        
        self.countdown_speed_var = tk.IntVar(value=50)
        ttk.Spinbox(countdown_anim_frame, from_=1, to=100, textvariable=self.countdown_speed_var, 
                   width=5).pack(side=tk.LEFT)
        
        # Update interval
        countdown_interval_frame = ttk.Frame(self.countdown_frame)
        countdown_interval_frame.grid(row=14, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(countdown_interval_frame, text="Update every:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.countdown_update_interval_var = tk.IntVar(value=60)
        ttk.Spinbox(countdown_interval_frame, from_=1, to=3600, textvariable=self.countdown_update_interval_var, 
                   width=5).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(countdown_interval_frame, text="second(s)").pack(side=tk.LEFT)
        
        # Send buttons
        button_frame = ttk.Frame(clock_frame)
        button_frame.pack(pady=(10, 0))
        
        self.send_clock_btn = ttk.Button(button_frame, text="Show Clock", 
                                         command=self.show_clock, state=tk.DISABLED)
        self.send_clock_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_clock_btn = ttk.Button(button_frame, text="Stop Live Clock", 
                                         command=self.stop_live_clock, state=tk.DISABLED)
        self.stop_clock_btn.pack(side=tk.LEFT)
        
        # Initialize clock update timer
        self.clock_timer = None
        self.clock_running = False
        
        # Update initial visibility
        self.update_clock_options()
        
    def create_stock_tab(self):
        """Create the stock market display tab"""
        stock_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(stock_frame, text="📈 Stocks")
        
        stock_frame.columnconfigure(1, weight=1)
        
        # Info
        info_label = ttk.Label(stock_frame, 
                              text="Display live stock market prices on your LED panel",
                              font=('TkDefaultFont', 9, 'italic'))
        info_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Stock ticker input
        ttk.Label(stock_frame, text="Stock Ticker:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        ticker_frame = ttk.Frame(stock_frame)
        ticker_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.stock_ticker_var = tk.StringVar(value="AAPL")
        ticker_entry = ttk.Entry(ticker_frame, textvariable=self.stock_ticker_var, width=15)
        ticker_entry.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        ttk.Label(ticker_frame, text="(e.g., AAPL, MSFT, TSLA, BTC-USD)", 
                 foreground="gray", font=('TkDefaultFont', 8)).grid(row=0, column=1, sticky=tk.W)
        
        # Display format
        ttk.Label(stock_frame, text="Display Format:").grid(row=2, column=0, sticky=tk.W, pady=(10, 5))
        
        self.stock_format_var = tk.StringVar(value="price_change")
        format_frame = ttk.Frame(stock_frame)
        format_frame.grid(row=2, column=1, sticky=tk.W, pady=(10, 5))
        
        ttk.Radiobutton(format_frame, text="Price + Change", 
                       variable=self.stock_format_var, value="price_change").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="Price Only", 
                       variable=self.stock_format_var, value="price_only").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="Ticker + Price", 
                       variable=self.stock_format_var, value="ticker_price").pack(anchor=tk.W)
        
        # Background color
        ttk.Label(stock_frame, text="Background:").grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        
        stock_bg_frame = ttk.Frame(stock_frame)
        stock_bg_frame.grid(row=3, column=1, sticky=tk.W, pady=(0, 5))
        
        self.stock_bg_color = "#FFFFFF"
        self.stock_bg_canvas = tk.Canvas(stock_bg_frame, width=30, height=20, 
                                        bg=self.stock_bg_color, relief=tk.SUNKEN)
        self.stock_bg_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(stock_bg_frame, text="Choose", command=self.choose_stock_bg_color).pack(side=tk.LEFT)

        # Sprite font
        stock_sprite_frame = ttk.Frame(stock_frame)
        stock_sprite_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        self.stock_use_sprite_var = tk.BooleanVar(value=True)
        ttk.Label(stock_sprite_frame, text="Sprite Font:").grid(row=0, column=0, sticky=tk.W)
        self.stock_sprite_font_var = tk.StringVar(value=self.settings.get('stock_sprite_font_name', ''))
        self.stock_sprite_font_combo = ttk.Combobox(stock_sprite_frame, textvariable=self.stock_sprite_font_var, state="readonly")
        self.stock_sprite_font_combo.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        self.stock_sprite_font_combo.bind('<<ComboboxSelected>>', lambda e: self.update_stock_sprite_settings())

        ttk.Label(stock_sprite_frame, text="Static delay (s):").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.stock_static_delay_var = tk.IntVar(value=self.settings.get('stock_static_delay_seconds', 2))
        ttk.Spinbox(stock_sprite_frame, from_=1, to=30, textvariable=self.stock_static_delay_var, width=5,
            command=self.update_stock_sprite_settings).grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        # Animation
        ttk.Label(stock_frame, text="Animation:").grid(row=5, column=0, sticky=tk.W, pady=(10, 5))
        
        self.stock_animation_var = tk.IntVar(value=1)
        animation_frame = ttk.Frame(stock_frame)
        animation_frame.grid(row=5, column=1, sticky=tk.W, pady=(10, 5))
        
        animations = [("Static", 0), ("Scroll Left", 1), ("Scroll Right", 2)]
        for text, value in animations:
            ttk.Radiobutton(animation_frame, text=text, variable=self.stock_animation_var, 
                          value=value).pack(side=tk.LEFT, padx=(0, 10))
        
        # Speed
        ttk.Label(stock_frame, text="Scroll Speed:").grid(row=6, column=0, sticky=tk.W, pady=(0, 5))
        
        self.stock_speed_var = tk.IntVar(value=30)
        speed_frame = ttk.Frame(stock_frame)
        speed_frame.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Scale(speed_frame, from_=1, to=100, variable=self.stock_speed_var, 
                 orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(speed_frame, textvariable=self.stock_speed_var).pack(side=tk.LEFT)
        
        # Auto-refresh
        ttk.Label(stock_frame, text="Auto Refresh:").grid(row=7, column=0, sticky=tk.W, pady=(10, 5))
        
        refresh_frame = ttk.Frame(stock_frame)
        refresh_frame.grid(row=7, column=1, sticky=tk.W, pady=(10, 5))
        
        self.stock_auto_refresh_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(refresh_frame, text="Enable auto-refresh every", 
                       variable=self.stock_auto_refresh_var).pack(side=tk.LEFT, padx=(0, 5))
        
        self.stock_refresh_interval_var = tk.IntVar(value=60)
        ttk.Spinbox(refresh_frame, from_=30, to=300, increment=30, 
                   textvariable=self.stock_refresh_interval_var, width=5).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(refresh_frame, text="seconds").pack(side=tk.LEFT)
        
        # Current stock info display
        self.stock_info_frame = ttk.LabelFrame(stock_frame, text="Stock Information", padding="10")
        self.stock_info_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(15, 10))
        
        self.stock_info_label = ttk.Label(self.stock_info_frame, text="Fetch stock data to see information", 
                                         foreground="gray")
        self.stock_info_label.pack()
        
        # Buttons
        button_frame = ttk.Frame(stock_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(button_frame, text="📊 Fetch Stock Data", 
                  command=self.fetch_stock_data).pack(side=tk.LEFT, padx=(0, 5))
        
        self.send_stock_btn = ttk.Button(button_frame, text="📤 Send to Display", 
                                        command=self.send_stock_to_display, state=tk.DISABLED)
        self.send_stock_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(button_frame, text="💾 Save as Preset", 
                  command=self.save_stock_preset).pack(side=tk.LEFT)
        
        # Store stock data
        self.current_stock_data = None
        self.stock_refresh_job = None
    
    def format_stock_price(self, price):
        """Format stock price to maximum 8 characters including $"""
        # Format: $XXXX.XX (8 chars max)
        if price >= 10000:
            # For prices >= 10000, use K notation: $12.34K
            return f"${price/1000:.2f}K"
        elif price >= 1000:
            # For prices 1000-9999, show 1-2 decimals: $1234.56
            formatted = f"${price:.2f}"
            if len(formatted) > 8:
                formatted = f"${price:.1f}"
            if len(formatted) > 8:
                formatted = f"${price:.0f}"
            return formatted
        elif price >= 100:
            # For prices 100-999, show 2 decimals: $123.45
            return f"${price:.2f}"
        elif price >= 10:
            # For prices 10-99, show 2-3 decimals: $12.345
            formatted = f"${price:.3f}"
            if len(formatted) > 8:
                formatted = f"${price:.2f}"
            return formatted
        else:
            # For prices < 10, show up to 4 decimals: $1.2345
            formatted = f"${price:.4f}"
            if len(formatted) > 8:
                formatted = f"${price:.3f}"
            if len(formatted) > 8:
                formatted = f"${price:.2f}"
            return formatted
    
    def choose_stock_color(self):
        """Choose text color for stock display"""
        color = colorchooser.askcolor(initialcolor=self.stock_text_color, title="Choose Text Color")
        if color[1]:
            self.stock_text_color = color[1]
            self.stock_color_canvas.config(bg=self.stock_text_color)
    
    def choose_stock_bg_color(self):
        """Choose background color for stock display"""
        color = colorchooser.askcolor(initialcolor=self.stock_bg_color, title="Choose Background Color")
        if color[1]:
            self.stock_bg_color = color[1]
            self.stock_bg_canvas.config(bg=self.stock_bg_color)
    
    def fetch_stock_data(self):
        """Fetch current stock data"""
        ticker = self.stock_ticker_var.get().strip().upper()
        if not ticker:
            messagebox.showwarning("No Ticker", "Please enter a stock ticker symbol")
            return
        
        # Show loading message
        self.stock_info_label.config(text=f"Fetching data for {ticker}...", foreground="blue")
        
        def fetch_task():
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                info = stock.info
                
                # Get current price and change
                current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
                
                if current_price is None:
                    self.root.after(0, lambda: self.stock_info_label.config(
                        text=f"Could not fetch data for {ticker}. Check ticker symbol.", 
                        foreground="red"))
                    return
                
                change = current_price - previous_close if previous_close else 0
                change_percent = (change / previous_close * 100) if previous_close else 0
                
                stock_name = info.get('shortName', ticker)
                
                self.current_stock_data = {
                    'ticker': ticker,
                    'name': stock_name,
                    'price': current_price,
                    'change': change,
                    'change_percent': change_percent,
                    'previous_close': previous_close
                }
                
                # Update UI
                def update_ui():
                    change_symbol = "▲" if change >= 0 else "▼"
                    change_color = "green" if change >= 0 else "red"
                    
                    info_text = f"{stock_name} ({ticker})\n"
                    info_text += f"Price: ${current_price:.2f}\n"
                    info_text += f"Change: {change_symbol} ${abs(change):.2f} ({change_percent:+.2f}%)"
                    
                    self.stock_info_label.config(text=info_text, foreground=change_color)
                    self.send_stock_btn.config(state=tk.NORMAL)
                
                self.root.after(0, update_ui)
                
            except ImportError:
                self.root.after(0, lambda: messagebox.showerror(
                    "Missing Library", 
                    "yfinance library not installed.\n\nInstall with: pip install yfinance"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.stock_info_label.config(
                    text=f"Error: {error_msg}", foreground="red"))
        
        threading.Thread(target=fetch_task, daemon=True).start()
    
    def send_stock_to_display(self):
        """Send stock data to the LED display"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first")
            return
        
        if not self.current_stock_data:
            messagebox.showwarning("No Data", "Please fetch stock data first")
            return
        
        self._stop_active_display_tasks()
        
        # Format text based on selected format
        format_type = self.stock_format_var.get()
        stock = self.current_stock_data
        
        # Format price to max 7 characters
        price_str = self.format_stock_price(stock['price'])
        
        if format_type == "price_change":
            change_symbol = "↑" if stock['change'] >= 0 else "↓"
            text = f"{price_str} {change_symbol}{abs(stock['change_percent']):.1f}%"
        elif format_type == "price_only":
            text = price_str
        else:  # ticker_price
            text = f"{stock['ticker']} {price_str}"
        
        def send_text_value(value_text):
            def send_task():
                try:
                    font = self._get_sprite_font_by_name(self.stock_sprite_font_var.get().strip())
                    if not font:
                        raise Exception("Sprite font not found")
                    anim = self.stock_animation_var.get()
                    if anim in (1, 2):
                        line_img, sprite_err = self._build_sprite_text_line_image(
                            value_text,
                            font.get('path', ''),
                            font.get('order', ''),
                            font.get('cols', 1),
                            self.stock_bg_color
                        )
                        if line_img is None:
                            raise Exception(sprite_err or "Sprite render failed")
                        direction = "right" if anim == 2 else "left"
                        self._start_sprite_scroll(line_img, self.stock_bg_color, self.stock_speed_var.get(), direction=direction)
                        return
                    sprite_img, sprite_err = self._build_sprite_text_image(
                        value_text,
                        font.get('path', ''),
                        font.get('order', ''),
                        font.get('cols', 1),
                        self.stock_bg_color
                    )
                    if sprite_img is None:
                        raise Exception(sprite_err or "Sprite render failed")
                    tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_stock_sprite.png')
                    sprite_img.save(tmp_path, 'PNG')
                    result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                    if asyncio.iscoroutine(result):
                        self.run_async(result)
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send: {error_msg}"))

            threading.Thread(target=send_task, daemon=True).start()

        def start_static_cycle():
            if self.stock_static_timer:
                self.root.after_cancel(self.stock_static_timer)
            state = {'show_ticker': True}
            delay_ms = max(1, int(self.stock_static_delay_var.get() or 2)) * 1000

            def tick():
                if format_type == "ticker_price":
                    send_text_value(stock['ticker'] if state['show_ticker'] else price_str)
                    state['show_ticker'] = not state['show_ticker']
                elif format_type == "price_change":
                    change_symbol = "↑" if stock['change'] >= 0 else "↓"
                    change_text = f"{change_symbol}{abs(stock['change_percent']):.1f}%"
                    send_text_value(price_str if state['show_ticker'] else change_text)
                    state['show_ticker'] = not state['show_ticker']
                else:
                    send_text_value(price_str)
                self.stock_static_timer = self.root.after(delay_ms, tick)

            tick()

        if self.stock_animation_var.get() == 0 and format_type in ("ticker_price", "price_change"):
            start_static_cycle()
        else:
            send_text_value(text)

        # Schedule auto-refresh if enabled
        if self.stock_auto_refresh_var.get():
            def auto_refresh():
                self.fetch_stock_data()
                # Wait a bit for data to be fetched, then send
                self.root.after(2000, self.send_stock_to_display)

            # Cancel previous job if exists
            if self.stock_refresh_job:
                self.root.after_cancel(self.stock_refresh_job)

            interval_ms = self.stock_refresh_interval_var.get() * 1000
            self.stock_refresh_job = self.root.after(interval_ms, auto_refresh)
    
    def save_stock_preset(self):
        """Save current stock configuration as a preset"""
        # Ask for preset name
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Stock Preset")
        dialog.geometry("400x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Preset Name:").pack(pady=(20, 5))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=(0, 10))
        name_entry.insert(0, f"Stock - {self.stock_ticker_var.get()}")
        name_entry.focus()
        name_entry.select_range(0, tk.END)
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("No Name", "Please enter a preset name")
                return
            
            preset = {
                "name": name,
                "type": "stock",
                "ticker": self.stock_ticker_var.get(),
                "format": self.stock_format_var.get(),
                "bg_color": self.stock_bg_color,
                "animation": self.stock_animation_var.get(),
                "speed": self.stock_speed_var.get(),
                "auto_refresh": self.stock_auto_refresh_var.get(),
                "refresh_interval": self.stock_refresh_interval_var.get(),
                "stock_sprite_font_name": self.stock_sprite_font_var.get().strip(),
                "stock_static_delay_seconds": int(self.stock_static_delay_var.get() or 2)
            }
            
            self.presets.append(preset)
            self.save_presets()
            self.refresh_preset_buttons()
            dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save).pack(pady=10)
    
    def create_youtube_tab(self):
        """Create the YouTube stats display tab"""
        youtube_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(youtube_frame, text="📺 YouTube")
        
        youtube_frame.columnconfigure(1, weight=1)
        
        # Info
        info_label = ttk.Label(youtube_frame, 
                              text="Display YouTube channel statistics on your LED panel",
                              font=('TkDefaultFont', 9, 'italic'))
        info_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # API Key setup
        api_frame = ttk.LabelFrame(youtube_frame, text="⚙️ API Setup", padding="10")
        api_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(api_frame, text="YouTube API Key:", font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        ttk.Label(api_frame, text="Get free API key from: https://console.cloud.google.com/apis/credentials", 
                 foreground="blue", font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))
        
        key_entry_frame = ttk.Frame(api_frame)
        key_entry_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.youtube_api_key_var = tk.StringVar()
        ttk.Entry(key_entry_frame, textvariable=self.youtube_api_key_var, width=50, show="*").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(key_entry_frame, text="Save Key", command=self.save_youtube_api_key).pack(side=tk.LEFT)
        
        # Channel input
        ttk.Label(youtube_frame, text="Channel ID/Handle:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        channel_frame = ttk.Frame(youtube_frame)
        channel_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.youtube_channel_var = tk.StringVar(value="@MrBeast")
        ttk.Entry(channel_frame, textvariable=self.youtube_channel_var, width=30).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        ttk.Label(channel_frame, text="(e.g., @MrBeast or UCX6OQ3DkcsbYNE6H8uQQuVA)", 
                 foreground="gray", font=('TkDefaultFont', 8)).grid(row=0, column=1, sticky=tk.W)
        
        # Background
        ttk.Label(youtube_frame, text="Background:").grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        
        yt_bg_frame = ttk.Frame(youtube_frame)
        yt_bg_frame.grid(row=3, column=1, sticky=tk.W, pady=(0, 5))
        
        self.youtube_bg_color = "#FFFFFF"
        self.youtube_bg_canvas = tk.Canvas(yt_bg_frame, width=30, height=20, 
                                          bg=self.youtube_bg_color, relief=tk.SUNKEN)
        self.youtube_bg_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(yt_bg_frame, text="Choose", command=self.choose_youtube_bg_color).pack(side=tk.LEFT)
        
        # Sprite font
        yt_sprite_frame = ttk.Frame(youtube_frame)
        yt_sprite_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        yt_sprite_frame.columnconfigure(1, weight=1)

        self.youtube_use_sprite_var = tk.BooleanVar(value=True)
        ttk.Label(yt_sprite_frame, text="Sprite Font:").grid(row=0, column=0, sticky=tk.W, pady=(5, 0))
        self.youtube_sprite_font_var = tk.StringVar(value=self.settings.get('youtube_sprite_font_name', ''))
        self.youtube_sprite_font_combo = ttk.Combobox(yt_sprite_frame, textvariable=self.youtube_sprite_font_var, state="readonly")
        self.youtube_sprite_font_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        self.youtube_sprite_font_combo.bind('<<ComboboxSelected>>', lambda e: self.update_youtube_sprite_settings())

        # Logo before stats
        yt_logo_frame = ttk.Frame(youtube_frame)
        yt_logo_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        yt_logo_frame.columnconfigure(1, weight=1)

        self.youtube_show_logo_var = tk.BooleanVar(value=True)
        ttk.Label(yt_logo_frame, text="Logo PNG:").grid(row=0, column=0, sticky=tk.W, pady=(5, 0))
        self.youtube_logo_path_var = tk.StringVar(value=self.settings.get('youtube_logo_path', os.path.join("Gallery", "Sprites", "YT-btn.png")))
        ttk.Entry(yt_logo_frame, textvariable=self.youtube_logo_path_var, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=(5, 0))
        ttk.Button(yt_logo_frame, text="Browse", command=self.browse_youtube_logo).grid(row=0, column=2, sticky=tk.W, pady=(5, 0))
        ttk.Label(yt_logo_frame, text="Supported resolution: 14x16 PNG", foreground="gray").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0)
        )

        # Auto-refresh
        ttk.Label(youtube_frame, text="Auto Refresh:").grid(row=6, column=0, sticky=tk.W, pady=(10, 5))

        yt_refresh_frame = ttk.Frame(youtube_frame)
        yt_refresh_frame.grid(row=6, column=1, sticky=tk.W, pady=(10, 5))
        
        self.youtube_auto_refresh_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(yt_refresh_frame, text="Enable auto-refresh every", 
                       variable=self.youtube_auto_refresh_var).pack(side=tk.LEFT, padx=(0, 5))
        
        self.youtube_refresh_interval_var = tk.IntVar(value=300)
        ttk.Spinbox(yt_refresh_frame, from_=60, to=3600, increment=60, 
                   textvariable=self.youtube_refresh_interval_var, width=5).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(yt_refresh_frame, text="seconds").pack(side=tk.LEFT)
        
        # Stats display
        self.youtube_info_frame = ttk.LabelFrame(youtube_frame, text="Channel Statistics", padding="10")
        self.youtube_info_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(15, 10))
        
        self.youtube_info_label = ttk.Label(self.youtube_info_frame, text="Fetch channel data to see statistics", 
                                           foreground="gray")
        self.youtube_info_label.pack()
        
        # Buttons
        yt_btn_frame = ttk.Frame(youtube_frame)
        yt_btn_frame.grid(row=8, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(yt_btn_frame, text="📊 Fetch Stats", 
                  command=self.fetch_youtube_stats).pack(side=tk.LEFT, padx=(0, 5))
        
        self.send_youtube_btn = ttk.Button(yt_btn_frame, text="📤 Send to Display", 
                                          command=self.send_youtube_to_display, state=tk.DISABLED)
        self.send_youtube_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(yt_btn_frame, text="💾 Save as Preset", 
                  command=self.save_youtube_preset).pack(side=tk.LEFT)
        
        # Store data
        self.current_youtube_data = None
        self.youtube_refresh_job = None
        
        # Load saved API key
        self.load_youtube_api_key()
    
    def create_weather_tab(self):
        """Create the weather display tab"""
        weather_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(weather_frame, text="🌤️ Weather")
        
        weather_frame.columnconfigure(1, weight=1)
        
        # Info
        info_label = ttk.Label(weather_frame, 
                              text="Display current weather conditions on your LED panel",
                              font=('TkDefaultFont', 9, 'italic'))
        info_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # API Key setup
        api_frame = ttk.LabelFrame(weather_frame, text="⚙️ API Setup", padding="10")
        api_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(api_frame, text="OpenWeatherMap API Key:", font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        ttk.Label(api_frame, text="Get free API key from: https://openweathermap.org/api", 
                 foreground="blue", font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))
        
        weather_key_frame = ttk.Frame(api_frame)
        weather_key_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.weather_api_key_var = tk.StringVar()
        ttk.Entry(weather_key_frame, textvariable=self.weather_api_key_var, width=50, show="*").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(weather_key_frame, text="Save Key", command=self.save_weather_api_key).pack(side=tk.LEFT)
        
        # Location
        ttk.Label(weather_frame, text="Location:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        location_frame = ttk.Frame(weather_frame)
        location_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.weather_location_var = tk.StringVar(value="London")
        ttk.Entry(location_frame, textvariable=self.weather_location_var, width=30).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        ttk.Label(location_frame, text="(City name or Zip code)", 
                 foreground="gray", font=('TkDefaultFont', 8)).grid(row=0, column=1, sticky=tk.W)
        
        # Temperature unit
        ttk.Label(weather_frame, text="Temperature Unit:").grid(row=3, column=0, sticky=tk.W, pady=(10, 5))
        
        self.weather_unit_var = tk.StringVar(value="metric")
        unit_frame = ttk.Frame(weather_frame)
        unit_frame.grid(row=3, column=1, sticky=tk.W, pady=(10, 5))
        
        ttk.Radiobutton(unit_frame, text="Celsius (°C)", variable=self.weather_unit_var, value="metric").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(unit_frame, text="Fahrenheit (°F)", variable=self.weather_unit_var, value="imperial").pack(side=tk.LEFT)
        
        # Display format
        ttk.Label(weather_frame, text="Display Format:").grid(row=4, column=0, sticky=tk.W, pady=(10, 5))
        
        self.weather_format_var = tk.StringVar(value="temp_condition")
        weather_fmt_frame = ttk.Frame(weather_frame)
        weather_fmt_frame.grid(row=4, column=1, sticky=tk.W, pady=(10, 5))
        
        ttk.Radiobutton(weather_fmt_frame, text="Temp + Condition (23°C Sunny)", 
                       variable=self.weather_format_var, value="temp_condition").pack(anchor=tk.W)
        ttk.Radiobutton(weather_fmt_frame, text="Temp Only (23°C)", 
                       variable=self.weather_format_var, value="temp_only").pack(anchor=tk.W)
        ttk.Radiobutton(weather_fmt_frame, text="City + Temp (London 23°C)", 
                       variable=self.weather_format_var, value="city_temp").pack(anchor=tk.W)
        ttk.Radiobutton(weather_fmt_frame, text="Full (London 23°C Sunny)", 
                       variable=self.weather_format_var, value="full").pack(anchor=tk.W)
        
        # Colors
        ttk.Label(weather_frame, text="Text Color:").grid(row=5, column=0, sticky=tk.W, pady=(10, 5))
        
        weather_color_frame = ttk.Frame(weather_frame)
        weather_color_frame.grid(row=5, column=1, sticky=tk.W, pady=(10, 5))
        
        self.weather_text_color = "#00FFFF"
        self.weather_color_canvas = tk.Canvas(weather_color_frame, width=30, height=20, 
                                             bg=self.weather_text_color, relief=tk.SUNKEN)
        self.weather_color_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(weather_color_frame, text="Choose", command=self.choose_weather_color).pack(side=tk.LEFT)
        
        # Background
        ttk.Label(weather_frame, text="Background:").grid(row=6, column=0, sticky=tk.W, pady=(0, 5))
        
        weather_bg_frame = ttk.Frame(weather_frame)
        weather_bg_frame.grid(row=6, column=1, sticky=tk.W, pady=(0, 5))
        
        self.weather_bg_color = "#FFFFFF"
        self.weather_bg_canvas = tk.Canvas(weather_bg_frame, width=30, height=20, 
                                          bg=self.weather_bg_color, relief=tk.SUNKEN)
        self.weather_bg_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(weather_bg_frame, text="Choose", command=self.choose_weather_bg_color).pack(side=tk.LEFT)

        # Temperature images
        ttk.Label(weather_frame, text="Temp Images:").grid(row=7, column=0, sticky=tk.W, pady=(10, 5))
        temp_img_frame = ttk.Frame(weather_frame)
        temp_img_frame.grid(row=7, column=1, sticky=(tk.W, tk.E), pady=(10, 5))
        temp_img_frame.columnconfigure(0, weight=1)

        self.weather_temp_image_dir_var = tk.StringVar(value=self.settings.get('weather_temp_image_dir', ''))
        ttk.Entry(temp_img_frame, textvariable=self.weather_temp_image_dir_var, width=30).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(temp_img_frame, text="Browse", command=self.browse_weather_temp_image_dir).grid(row=0, column=1)

        self.weather_use_temp_images_var = tk.BooleanVar(value=self.settings.get('weather_use_temp_images', False))
        ttk.Checkbutton(
            temp_img_frame,
            text="Use temp images (temp_plus_30.png, temp_minus_5.png)",
            variable=self.weather_use_temp_images_var,
            command=self.update_weather_temp_image_settings
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        # Animation
        ttk.Label(weather_frame, text="Animation:").grid(row=8, column=0, sticky=tk.W, pady=(10, 5))
        
        self.weather_animation_var = tk.IntVar(value=1)
        weather_anim_frame = ttk.Frame(weather_frame)
        weather_anim_frame.grid(row=8, column=1, sticky=tk.W, pady=(10, 5))
        
        for text, value in [("Static", 0), ("Scroll Left", 1), ("Scroll Right", 2)]:
            ttk.Radiobutton(weather_anim_frame, text=text, variable=self.weather_animation_var, 
                          value=value).pack(side=tk.LEFT, padx=(0, 10))
        
        # Speed
        ttk.Label(weather_frame, text="Scroll Speed:").grid(row=9, column=0, sticky=tk.W, pady=(0, 5))
        
        self.weather_speed_var = tk.IntVar(value=30)
        weather_speed_frame = ttk.Frame(weather_frame)
        weather_speed_frame.grid(row=9, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Scale(weather_speed_frame, from_=1, to=100, variable=self.weather_speed_var, 
                 orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(weather_speed_frame, textvariable=self.weather_speed_var).pack(side=tk.LEFT)
        
        # Auto-refresh
        ttk.Label(weather_frame, text="Auto Refresh:").grid(row=10, column=0, sticky=tk.W, pady=(10, 5))
        
        weather_refresh_frame = ttk.Frame(weather_frame)
        weather_refresh_frame.grid(row=10, column=1, sticky=tk.W, pady=(10, 5))
        
        self.weather_auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(weather_refresh_frame, text="Enable auto-refresh every", 
                       variable=self.weather_auto_refresh_var).pack(side=tk.LEFT, padx=(0, 5))
        
        self.weather_refresh_interval_var = tk.IntVar(value=600)
        ttk.Spinbox(weather_refresh_frame, from_=300, to=3600, increment=300, 
                   textvariable=self.weather_refresh_interval_var, width=5).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(weather_refresh_frame, text="seconds").pack(side=tk.LEFT)
        
        # Weather info display
        self.weather_info_frame = ttk.LabelFrame(weather_frame, text="Current Weather", padding="10")
        self.weather_info_frame.grid(row=11, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(15, 10))
        
        self.weather_info_label = ttk.Label(self.weather_info_frame, text="Fetch weather data to see conditions", 
                                           foreground="gray")
        self.weather_info_label.pack()
        
        # Buttons
        weather_btn_frame = ttk.Frame(weather_frame)
        weather_btn_frame.grid(row=12, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(weather_btn_frame, text="🌤️ Fetch Weather", 
                  command=self.fetch_weather_data).pack(side=tk.LEFT, padx=(0, 5))
        
        self.send_weather_btn = ttk.Button(weather_btn_frame, text="📤 Send to Display", 
                                          command=self.send_weather_to_display, state=tk.DISABLED)
        self.send_weather_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(weather_btn_frame, text="💾 Save as Preset", 
                  command=self.save_weather_preset).pack(side=tk.LEFT)
        
        # Store data
        self.current_weather_data = None
        self.weather_refresh_job = None
        
        # Load saved API key
        self.load_weather_api_key()
    
    def create_animations_tab(self):
        """Create the pixel art animations tab"""
        anim_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(anim_frame, text="🎨 Animations")
        
        anim_frame.columnconfigure(1, weight=1)
        
        # Info
        info_label = ttk.Label(anim_frame, 
                              text="Display animated pixel art effects on your LED panel",
                              font=('TkDefaultFont', 9, 'italic'))
        info_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Animation type
        ttk.Label(anim_frame, text="Animation Type:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        self.anim_type_var = tk.StringVar(value="game_of_life")
        type_frame = ttk.Frame(anim_frame)
        type_frame.grid(row=1, column=1, sticky=tk.W, pady=(0, 5))
        
        ttk.Radiobutton(type_frame, text="Conway's Game of Life", 
                       variable=self.anim_type_var, value="game_of_life",
                       command=self.update_anim_options).pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Matrix Rain", 
                       variable=self.anim_type_var, value="matrix",
                       command=self.update_anim_options).pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Fire Effect", 
                       variable=self.anim_type_var, value="fire",
                       command=self.update_anim_options).pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Starfield", 
                       variable=self.anim_type_var, value="starfield",
                       command=self.update_anim_options).pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Plasma", 
                       variable=self.anim_type_var, value="plasma",
                       command=self.update_anim_options).pack(anchor=tk.W)
        
        # Color scheme
        ttk.Label(anim_frame, text="Color Scheme:").grid(row=2, column=0, sticky=tk.W, pady=(10, 5))
        
        self.anim_color_scheme_var = tk.StringVar(value="green")
        color_frame = ttk.Frame(anim_frame)
        color_frame.grid(row=2, column=1, sticky=tk.W, pady=(10, 5))
        
        schemes = [("Green (Matrix)", "green"), ("Blue", "blue"), ("Red (Fire)", "red"), 
                  ("Rainbow", "rainbow"), ("White", "white")]
        for text, value in schemes:
            ttk.Radiobutton(color_frame, text=text, variable=self.anim_color_scheme_var, 
                          value=value).pack(anchor=tk.W)
        
        # Speed/FPS
        ttk.Label(anim_frame, text="Animation Speed:").grid(row=3, column=0, sticky=tk.W, pady=(10, 5))
        
        self.anim_speed_var = tk.IntVar(value=10)
        anim_speed_frame = ttk.Frame(anim_frame)
        anim_speed_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=(10, 5))
        
        ttk.Scale(anim_speed_frame, from_=1, to=30, variable=self.anim_speed_var, 
                 orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(anim_speed_frame, textvariable=self.anim_speed_var).pack(side=tk.LEFT)
        ttk.Label(anim_speed_frame, text="FPS").pack(side=tk.LEFT, padx=(5, 0))
        
        # Duration
        ttk.Label(anim_frame, text="Duration:").grid(row=4, column=0, sticky=tk.W, pady=(0, 5))
        
        duration_frame = ttk.Frame(anim_frame)
        duration_frame.grid(row=4, column=1, sticky=tk.W, pady=(0, 5))
        
        self.anim_duration_var = tk.IntVar(value=60)
        ttk.Spinbox(duration_frame, from_=10, to=300, increment=10, 
                   textvariable=self.anim_duration_var, width=5).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(duration_frame, text="seconds (0 = infinite)").pack(side=tk.LEFT)
        
        # Game of Life specific options
        self.gol_options_frame = ttk.LabelFrame(anim_frame, text="Game of Life Options", padding="10")
        self.gol_options_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 5))
        
        ttk.Label(self.gol_options_frame, text="Initial Density:").pack(anchor=tk.W)
        self.gol_density_var = tk.IntVar(value=30)
        density_frame = ttk.Frame(self.gol_options_frame)
        density_frame.pack(fill=tk.X)
        
        ttk.Scale(density_frame, from_=10, to=50, variable=self.gol_density_var, 
                 orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(density_frame, textvariable=self.gol_density_var).pack(side=tk.LEFT)
        ttk.Label(density_frame, text="%").pack(side=tk.LEFT, padx=(2, 0))
        
        # Preview
        preview_frame = ttk.LabelFrame(anim_frame, text="Preview", padding="10")
        preview_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 5))
        anim_frame.rowconfigure(6, weight=1)
        
        self.anim_preview_label = ttk.Label(preview_frame, text="Animation will be generated when sent to display", 
                                           foreground="gray")
        self.anim_preview_label.pack()
        
        # Buttons
        anim_btn_frame = ttk.Frame(anim_frame)
        anim_btn_frame.grid(row=7, column=0, columnspan=2, pady=(10, 0))
        
        self.send_anim_btn = ttk.Button(anim_btn_frame, text="▶️ Start Animation", 
                                        command=self.send_animation_to_display, state=tk.NORMAL if self.is_connected else tk.DISABLED)
        self.send_anim_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_anim_btn = ttk.Button(anim_btn_frame, text="⏹️ Stop Animation", 
                                       command=self.stop_animation, state=tk.DISABLED)
        self.stop_anim_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(anim_btn_frame, text="💾 Save as Preset", 
                  command=self.save_animation_preset).pack(side=tk.LEFT)
        
        # Store state
        self.animation_running = False
        self.animation_timer = None
        
        # Update initial visibility
        self.update_anim_options()
    
    # ===== YouTube Methods =====
    def save_youtube_api_key(self):
        """Save YouTube API key to settings"""
        api_key = self.youtube_api_key_var.get().strip()
        if api_key:
            self.secrets['youtube_api_key'] = api_key
            self.save_secrets()
            messagebox.showinfo("Success", "YouTube API key saved")
    
    def load_youtube_api_key(self):
        """Load YouTube API key from settings"""
        api_key = self.secrets.get('youtube_api_key', '')
        self.youtube_api_key_var.set(api_key)
    
    def choose_youtube_color(self):
        """Choose text color for YouTube display"""
        color = colorchooser.askcolor(initialcolor=self.youtube_text_color, title="Choose Text Color")
        if color[1]:
            self.youtube_text_color = color[1]
            self.youtube_color_canvas.config(bg=self.youtube_text_color)
    
    def choose_youtube_bg_color(self):
        """Choose background color for YouTube display"""
        color = colorchooser.askcolor(initialcolor=self.youtube_bg_color, title="Choose Background Color")
        if color[1]:
            self.youtube_bg_color = color[1]
            self.youtube_bg_canvas.config(bg=self.youtube_bg_color)
    
    def fetch_youtube_stats(self):
        """Fetch YouTube channel statistics"""
        channel_input = self.youtube_channel_var.get().strip()
        api_key = self.youtube_api_key_var.get().strip()
        
        if not api_key:
            messagebox.showwarning("No API Key", "Please enter your YouTube API key first")
            return
        
        if not channel_input:
            messagebox.showwarning("No Channel", "Please enter a channel ID or handle")
            return
        
        self.youtube_info_label.config(text=f"Fetching data for {channel_input}...", foreground="blue")
        
        def fetch_task():
            try:
                from googleapiclient.discovery import build
                
                youtube = build('youtube', 'v3', developerKey=api_key)
                
                # Handle both @handle and channel ID formats
                if channel_input.startswith('@'):
                    # Search for channel by handle
                    search_response = youtube.search().list(
                        q=channel_input,
                        type='channel',
                        part='id',
                        maxResults=1
                    ).execute()
                    
                    if not search_response.get('items'):
                        self.root.after(0, lambda: self.youtube_info_label.config(
                            text=f"Channel not found: {channel_input}", foreground="red"))
                        return
                    
                    channel_id = search_response['items'][0]['id']['channelId']
                else:
                    channel_id = channel_input
                
                # Get channel statistics
                channel_response = youtube.channels().list(
                    part='statistics,snippet',
                    id=channel_id
                ).execute()
                
                if not channel_response.get('items'):
                    self.root.after(0, lambda: self.youtube_info_label.config(
                        text=f"Channel not found: {channel_input}", foreground="red"))
                    return
                
                channel_data = channel_response['items'][0]
                stats = channel_data['statistics']
                snippet = channel_data['snippet']
                
                channel_title = snippet['title']
                subscribers = int(stats.get('subscriberCount', 0))
                views = int(stats.get('viewCount', 0))
                videos = int(stats.get('videoCount', 0))
                
                # Latest video lookup removed (single YouTube format)
                latest_video_views = 0
                
                self.current_youtube_data = {
                    'channel_title': channel_title,
                    'subscribers': subscribers,
                    'views': views,
                    'videos': videos,
                    'latest_video_views': latest_video_views
                }
                
                def update_ui():
                    info_text = f"{channel_title}\n"
                    info_text += f"Subscribers: {subscribers:,}\n"
                    info_text += f"Total Views: {views:,}\n"
                    info_text += f"Videos: {videos:,}"
                    
                    self.youtube_info_label.config(text=info_text, foreground="green")
                    self.send_youtube_btn.config(state=tk.NORMAL)
                
                self.root.after(0, update_ui)
                
            except ImportError:
                self.root.after(0, lambda: messagebox.showerror(
                    "Missing Library", 
                    "Google API library not installed.\n\nInstall with: pip install google-api-python-client"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.youtube_info_label.config(
                    text=f"Error: {error_msg}", foreground="red"))
        
        threading.Thread(target=fetch_task, daemon=True).start()
    
    def format_number(self, num):
        """Format large numbers with K/M/B suffixes"""
        if num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)
    
    def send_youtube_to_display(self):
        """Send YouTube stats to the LED display"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first")
            return
        
        if not self.current_youtube_data:
            messagebox.showwarning("No Data", "Please fetch YouTube data first")
            return
        
        self._stop_active_display_tasks()
        
        data = self.current_youtube_data
        text = self.format_number(data['subscribers'])

        try:
            subs_value = int(data['subscribers'])
        except Exception:
            subs_value = data.get('subscribers', 0) if isinstance(data, dict) else 0
        subs_digits = len(str(subs_value)) if isinstance(subs_value, int) else 0
        subs_text = str(subs_value) if subs_digits and subs_digits <= 7 else self.format_number(subs_value)

        self._stop_sprite_scroll()
        
        def send_stats():
            try:
                font = self._get_sprite_font_by_name(self.youtube_sprite_font_var.get().strip())
                if not font:
                    raise Exception("Sprite font not found")
                sprite_img, sprite_err = self._build_sprite_text_image(
                    text,
                    font.get('path', ''),
                    font.get('order', ''),
                    font.get('cols', 1),
                    self.youtube_bg_color
                )
                if sprite_img is None:
                    raise Exception(sprite_err or "Sprite render failed")
                tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_youtube_sprite.png')
                sprite_img.save(tmp_path, 'PNG')
                result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                if asyncio.iscoroutine(result):
                    self.run_async(result)

                if self.youtube_auto_refresh_var.get():
                    def auto_refresh():
                        self.fetch_youtube_stats()
                        self.root.after(2000, self.send_youtube_to_display)

                    if self.youtube_refresh_job:
                        self.root.after_cancel(self.youtube_refresh_job)

                    interval_ms = self.youtube_refresh_interval_var.get() * 1000
                    self.youtube_refresh_job = self.root.after(interval_ms, auto_refresh)
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send: {error_msg}"))

        def _send_logo_inline():
            logo_path = self._resolve_asset_path(self.youtube_logo_path_var.get().strip())
            if not logo_path or not os.path.exists(logo_path):
                return False, f"Logo file not found: {logo_path or self.youtube_logo_path_var.get().strip()}"
            try:
                logo = Image.open(logo_path).convert("RGBA")
                if logo.size != (14, 16):
                    logo = logo.resize((14, 16), Image.NEAREST)

                canvas = Image.new("RGBA", (64, 16), self.youtube_bg_color)
                canvas.paste(logo, (0, 0), logo)

                text_x = 14 + 2
                if self.youtube_use_sprite_var.get():
                    font = self._get_sprite_font_by_name(self.youtube_sprite_font_var.get().strip())
                    if not font:
                        raise Exception("Sprite font not found")
                    line_img, sprite_err = self._build_sprite_text_line_image(
                        subs_text,
                        font.get('path', ''),
                        font.get('order', ''),
                        font.get('cols', 1),
                        self.youtube_bg_color
                    )
                    if line_img is None:
                        raise Exception(sprite_err or "Sprite render failed")
                    if line_img.height != 16:
                        line_img = line_img.resize((line_img.width, 16), Image.NEAREST)
                    max_w = 64 - text_x
                    if line_img.width > max_w:
                        line_img = line_img.crop((0, 0, max_w, line_img.height))
                    paste_x = text_x + max(0, (max_w - line_img.width) // 2)
                    canvas.paste(line_img, (paste_x, 0))
                else:
                    draw = ImageDraw.Draw(canvas)
                    try:
                        font = ImageFont.truetype("arial.ttf", 10)
                    except Exception:
                        font = ImageFont.load_default()
                    bbox = draw.textbbox((0, 0), subs_text, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                    y = max(0, (16 - text_h) // 2)
                    x = text_x + max(0, ((64 - text_x) - text_w) // 2)
                    draw.text((x, y), subs_text, font=font, fill=self.youtube_text_color)

                tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_youtube_logo_inline.png')
                canvas.convert("RGB").save(tmp_path, 'PNG')
                result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
                return True, ""
            except Exception as e:
                return False, str(e)

        def send_task():
            try:
                ok, err = _send_logo_inline()
                if not ok:
                    self.root.after(0, lambda: messagebox.showwarning("Logo Not Found", err))
                else:
                    if self.youtube_auto_refresh_var.get():
                        def auto_refresh():
                            self.fetch_youtube_stats()
                            self.root.after(2000, self.send_youtube_to_display)

                        if self.youtube_refresh_job:
                            self.root.after_cancel(self.youtube_refresh_job)

                        interval_ms = self.youtube_refresh_interval_var.get() * 1000
                        self.youtube_refresh_job = self.root.after(interval_ms, auto_refresh)
                    return
                send_stats()
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send: {error_msg}"))

        threading.Thread(target=send_task, daemon=True).start()
    
    def save_youtube_preset(self):
        """Save YouTube configuration as preset"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Save YouTube Preset")
        dialog.geometry("400x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Preset Name:").pack(pady=(20, 5))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=(0, 10))
        name_entry.insert(0, f"YouTube - {self.youtube_channel_var.get()}")
        name_entry.focus()
        name_entry.select_range(0, tk.END)
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("No Name", "Please enter a preset name")
                return
            
            preset = {
                "name": name,
                "type": "youtube",
                "channel": self.youtube_channel_var.get(),
                "bg_color": self.youtube_bg_color,
                "auto_refresh": self.youtube_auto_refresh_var.get(),
                "refresh_interval": self.youtube_refresh_interval_var.get(),
                "youtube_use_sprite_font": self.youtube_use_sprite_var.get(),
                "youtube_sprite_font_name": self.youtube_sprite_font_var.get().strip(),
                "youtube_show_logo": self.youtube_show_logo_var.get(),
                "youtube_logo_path": self.youtube_logo_path_var.get().strip()
            }
            
            self.presets.append(preset)
            self.save_presets()
            self.refresh_preset_buttons()
            dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save).pack(pady=10)
    
    # ===== Weather Methods =====
    def save_weather_api_key(self):
        """Save weather API key to settings"""
        api_key = self.weather_api_key_var.get().strip()
        if api_key:
            self.secrets['weather_api_key'] = api_key
            self.save_secrets()
            messagebox.showinfo("Success", "Weather API key saved")
    
    def load_weather_api_key(self):
        """Load weather API key from settings"""
        api_key = self.secrets.get('weather_api_key', '')
        self.weather_api_key_var.set(api_key)
    
    def choose_weather_color(self):
        """Choose text color for weather display"""
        color = colorchooser.askcolor(initialcolor=self.weather_text_color, title="Choose Text Color")
        if color[1]:
            self.weather_text_color = color[1]
            self.weather_color_canvas.config(bg=self.weather_text_color)
    
    def choose_weather_bg_color(self):
        """Choose background color for weather display"""
        color = colorchooser.askcolor(initialcolor=self.weather_bg_color, title="Choose Background Color")
        if color[1]:
            self.weather_bg_color = color[1]
            self.weather_bg_canvas.config(bg=self.weather_bg_color)

    def browse_weather_temp_image_dir(self):
        """Select folder that contains temperature images"""
        folder = filedialog.askdirectory(title="Select temperature image folder")
        if folder:
            self.weather_temp_image_dir_var.set(folder)
            self.update_weather_temp_image_settings()

    def update_weather_temp_image_settings(self):
        """Persist weather temp image settings"""
        self.settings['weather_use_temp_images'] = self.weather_use_temp_images_var.get()
        self.settings['weather_temp_image_dir'] = self.weather_temp_image_dir_var.get().strip()
        self.save_settings()

    def _get_temp_image_path(self, temp_value, folder):
        """Resolve temperature image path based on current temp."""
        folder = self._resolve_asset_path(folder)
        if not folder:
            return None
        temp_int = int(round(temp_value))
        candidates = []
        if temp_int < 0:
            candidates.append(f"temp_minus_{abs(temp_int)}.png")
            candidates.append(f"temp_-{abs(temp_int)}.png")
        else:
            candidates.append(f"temp_plus_{temp_int}.png")
            candidates.append(f"temp_{temp_int}.png")
            if temp_int == 0:
                candidates.append("temp_0.png")
                candidates.append("temp_plus_0.png")
        for name in candidates:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
        return None
    
    def fetch_weather_data(self):
        """Fetch current weather data"""
        location = self.weather_location_var.get().strip()
        api_key = self.weather_api_key_var.get().strip()
        
        if not api_key:
            messagebox.showwarning("No API Key", "Please enter your OpenWeatherMap API key first")
            return
        
        if not location:
            messagebox.showwarning("No Location", "Please enter a location")
            return
        
        self.weather_info_label.config(text=f"Fetching weather for {location}...", foreground="blue")
        
        def fetch_task():
            try:
                import requests
                
                unit = self.weather_unit_var.get()
                url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units={unit}"
                
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    self.root.after(0, lambda: self.weather_info_label.config(
                        text=f"Error: {response.json().get('message', 'Unknown error')}", foreground="red"))
                    return
                
                data = response.json()
                
                temp = data['main']['temp']
                feels_like = data['main']['feels_like']
                condition = data['weather'][0]['main']
                description = data['weather'][0]['description']
                humidity = data['main']['humidity']
                wind_speed = data['wind']['speed']
                city_name = data['name']
                
                unit_symbol = "°C" if unit == "metric" else "°F"
                
                self.current_weather_data = {
                    'city': city_name,
                    'temp': temp,
                    'feels_like': feels_like,
                    'condition': condition,
                    'description': description,
                    'humidity': humidity,
                    'wind_speed': wind_speed,
                    'unit': unit_symbol
                }
                
                def update_ui():
                    info_text = f"{city_name}\n"
                    info_text += f"Temperature: {temp:.1f}°{unit_symbol}\n"
                    info_text += f"Feels like: {feels_like:.1f}°{unit_symbol}\n"
                    info_text += f"Condition: {description.title()}\n"
                    info_text += f"Humidity: {humidity}%"
                    
                    self.weather_info_label.config(text=info_text, foreground="green")
                    self.send_weather_btn.config(state=tk.NORMAL)
                
                self.root.after(0, update_ui)
                
            except ImportError:
                self.root.after(0, lambda: messagebox.showerror(
                    "Missing Library", 
                    "requests library not installed.\n\nInstall with: pip install requests"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.weather_info_label.config(
                    text=f"Error: {error_msg}", foreground="red"))
        
        threading.Thread(target=fetch_task, daemon=True).start()
    
    def send_weather_to_display(self):
        """Send weather data to the LED display"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first")
            return
        
        if not self.current_weather_data:
            messagebox.showwarning("No Data", "Please fetch weather data first")
            return
        
        self._stop_active_display_tasks()
        
        format_type = self.weather_format_var.get()
        data = self.current_weather_data
        
        unit = "c" if data['unit'] == "°C" else "f"
        temp_icon = "T"
        if format_type == "temp_condition":
            text = f"{temp_icon} {data['temp']:.0f}{unit} {data['condition']}"
        elif format_type == "temp_only":
            text = f"{temp_icon} {data['temp']:.0f}{unit}"
        elif format_type == "city_temp":
            text = f"{data['city']} {temp_icon} {data['temp']:.0f}{unit}"
        else:  # full
            text = f"{data['city']} {temp_icon} {data['temp']:.0f}{unit} {data['condition']}"
        
        def send_task():
            try:
                text_color = self.weather_text_color.lstrip('#')
                bg_color = self.weather_bg_color.lstrip('#')
                speed = 101 - self.weather_speed_var.get()

                temp_img_dir = self.weather_temp_image_dir_var.get().strip()
                if self.weather_use_temp_images_var.get() and temp_img_dir:
                    image_path = self._get_temp_image_path(data['temp'], temp_img_dir)
                    if image_path:
                        result = self.client.send_image(image_path, resize_method='crop', save_slot=0)
                        if asyncio.iscoroutine(result):
                            self.run_async(result)
                        return

                result = self.client.send_text(
                    text,
                    char_height=16,
                    color=text_color,
                    bg_color=bg_color,
                    animation=self.weather_animation_var.get(),
                    speed=speed,
                    rainbow_mode=0
                )
                
                if asyncio.iscoroutine(result):
                    self.run_async(result)
                
                if self.weather_auto_refresh_var.get():
                    def auto_refresh():
                        self.fetch_weather_data()
                        self.root.after(2000, self.send_weather_to_display)
                    
                    if self.weather_refresh_job:
                        self.root.after_cancel(self.weather_refresh_job)
                    
                    interval_ms = self.weather_refresh_interval_var.get() * 1000
                    self.weather_refresh_job = self.root.after(interval_ms, auto_refresh)
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send: {error_msg}"))
        
        threading.Thread(target=send_task, daemon=True).start()
    
    def save_weather_preset(self):
        """Save weather configuration as preset"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Weather Preset")
        dialog.geometry("400x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Preset Name:").pack(pady=(20, 5))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=(0, 10))
        name_entry.insert(0, f"Weather - {self.weather_location_var.get()}")
        name_entry.focus()
        name_entry.select_range(0, tk.END)
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("No Name", "Please enter a preset name")
                return
            
            preset = {
                "name": name,
                "type": "weather",
                "location": self.weather_location_var.get(),
                "unit": self.weather_unit_var.get(),
                "format": self.weather_format_var.get(),
                "text_color": self.weather_text_color,
                "bg_color": self.weather_bg_color,
                "animation": self.weather_animation_var.get(),
                "speed": self.weather_speed_var.get(),
                "auto_refresh": self.weather_auto_refresh_var.get(),
                "refresh_interval": self.weather_refresh_interval_var.get()
            }
            
            self.presets.append(preset)
            self.save_presets()
            self.refresh_preset_buttons()
            dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save).pack(pady=10)
    
    # ===== Animation Methods =====
    def update_anim_options(self):
        """Update visibility of animation options"""
        anim_type = self.anim_type_var.get()
        
        if anim_type == "game_of_life":
            self.gol_options_frame.grid()
        else:
            self.gol_options_frame.grid_remove()
    
    def generate_game_of_life_frame(self, width=64, height=16, state=None):
        """Generate one frame of Conway's Game of Life"""
        import numpy as np
        
        if state is None:
            # Initialize with random state
            density = self.gol_density_var.get() / 100
            state = np.random.random((height, width)) < density
        
        # Count neighbors
        padded = np.pad(state, 1, mode='wrap')
        neighbors = sum([
            padded[0:-2, 0:-2], padded[0:-2, 1:-1], padded[0:-2, 2:],
            padded[1:-1, 0:-2],                    padded[1:-1, 2:],
            padded[2:,   0:-2], padded[2:,   1:-1], padded[2:,   2:]
        ])
        
        # Apply rules
        new_state = (neighbors == 3) | (state & (neighbors == 2))
        
        return new_state
    
    def generate_animation_frame(self, frame_num, width=64, height=16):
        """Generate animation frame based on type"""
        import numpy as np
        
        anim_type = self.anim_type_var.get()
        color_scheme = self.anim_color_scheme_var.get()
        
        # Create RGB image
        img = Image.new('RGB', (width, height), (0, 0, 0))
        pixels = img.load()
        
        if anim_type == "game_of_life":
            if not hasattr(self, 'gol_state') or frame_num == 0:
                self.gol_state = self.generate_game_of_life_frame(width, height)
            else:
                self.gol_state = self.generate_game_of_life_frame(width, height, self.gol_state)
            
            # Apply color scheme
            for y in range(height):
                for x in range(width):
                    if self.gol_state[y, x]:
                        pixels[x, y] = self.get_color_for_scheme(color_scheme, frame_num, x, y)
        
        elif anim_type == "matrix":
            # Matrix rain effect
            if not hasattr(self, 'matrix_drops'):
                self.matrix_drops = [np.random.randint(-height, 0) for _ in range(width)]
            
            for x in range(width):
                self.matrix_drops[x] += 1
                if self.matrix_drops[x] > height:
                    self.matrix_drops[x] = np.random.randint(-height//2, 0)
                
                # Draw trail
                for trail in range(5):
                    y = self.matrix_drops[x] - trail
                    if 0 <= y < height:
                        brightness = max(0, 255 - trail * 50)
                        pixels[x, y] = (0, brightness, 0) if color_scheme == "green" else (brightness, brightness, brightness)
        
        elif anim_type == "fire":
            # Fire effect
            if not hasattr(self, 'fire_buffer'):
                self.fire_buffer = np.zeros((height, width))
            
            # Heat bottom row
            self.fire_buffer[-1, :] = np.random.randint(200, 256, width)
            
            # Propagate and cool
            for y in range(height-1):
                for x in range(width):
                    avg = (self.fire_buffer[y+1, (x-1)%width] + 
                          self.fire_buffer[y+1, x] + 
                          self.fire_buffer[y+1, (x+1)%width]) / 3
                    self.fire_buffer[y, x] = max(0, avg - np.random.randint(0, 10))
            
            # Apply fire colors
            for y in range(height):
                for x in range(width):
                    heat = int(self.fire_buffer[y, x])
                    if heat < 85:
                        pixels[x, y] = (heat * 3, 0, 0)
                    elif heat < 170:
                        pixels[x, y] = (255, (heat-85) * 3, 0)
                    else:
                        pixels[x, y] = (255, 255, (heat-170) * 3)
        
        elif anim_type == "starfield":
            # Starfield effect
            if not hasattr(self, 'stars'):
                self.stars = [(np.random.randint(0, width), np.random.randint(0, height), 
                              np.random.randint(1, 4)) for _ in range(30)]
            
            # Move stars
            new_stars = []
            for x, y, speed in self.stars:
                x += speed
                if x >= width:
                    x = 0
                    y = np.random.randint(0, height)
                new_stars.append((x, y, speed))
            self.stars = new_stars
            
            # Draw stars
            for x, y, speed in self.stars:
                brightness = 100 + speed * 50
                pixels[x, y] = self.get_color_for_scheme(color_scheme, frame_num, x, y, brightness)
        
        elif anim_type == "plasma":
            # Plasma effect
            for y in range(height):
                for x in range(width):
                    v = np.sin(x / 4.0 + frame_num / 10.0) + np.sin(y / 3.0 + frame_num / 15.0)
                    v = (v + 2) / 4 * 255
                    pixels[x, y] = self.get_color_for_scheme(color_scheme, int(v), x, y)
        
        return img
    
    def get_color_for_scheme(self, scheme, frame_num, x=0, y=0, brightness=255):
        """Get color based on scheme"""
        if scheme == "green":
            return (0, brightness, 0)
        elif scheme == "blue":
            return (0, 0, brightness)
        elif scheme == "red":
            return (brightness, 0, 0)
        elif scheme == "white":
            return (brightness, brightness, brightness)
        elif scheme == "rainbow":
            hue = (frame_num + x + y) % 360
            import colorsys
            rgb = colorsys.hsv_to_rgb(hue/360, 1.0, brightness/255)
            return tuple(int(c * 255) for c in rgb)
        return (brightness, brightness, brightness)
    
    def send_animation_to_display(self):
        """Send animation to the LED display"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first")
            return

        self._stop_active_display_tasks()
        
        self.animation_running = True
        self.send_anim_btn.config(state=tk.DISABLED)
        self.stop_anim_btn.config(state=tk.NORMAL)
        
        fps = self.anim_speed_var.get()
        frame_delay = 1000 // fps  # ms per frame
        duration = self.anim_duration_var.get()
        total_frames = duration * fps if duration > 0 else 9999999
        
        frame_count = [0]  # Use list to make it mutable in nested function
        
        # Reset animation state
        if hasattr(self, 'gol_state'):
            del self.gol_state
        if hasattr(self, 'matrix_drops'):
            del self.matrix_drops
        if hasattr(self, 'fire_buffer'):
            del self.fire_buffer
        if hasattr(self, 'stars'):
            del self.stars
        
        def send_next_frame():
            if not self.animation_running or frame_count[0] >= total_frames:
                self.stop_animation()
                return
            
            try:
                # Generate frame
                frame_img = self.generate_animation_frame(frame_count[0])
                
                # Save to temp file
                temp_path = os.path.join(tempfile.gettempdir(), 'ipixel_anim_frame.png')
                frame_img.save(temp_path, 'PNG')
                
                # Send to display synchronously to avoid overwhelming the device
                def send_task():
                    try:
                        import time
                        result = self.client.send_image(temp_path, resize_method='crop', save_slot=0)
                        if asyncio.iscoroutine(result):
                            self.run_async(result)
                        # Small delay to ensure device has time to process
                        time.sleep(0.05)  # 50ms delay between frames
                    except Exception as e:
                        print(f"Frame send error: {e}")
                
                # Send synchronously in thread and wait
                thread = threading.Thread(target=send_task, daemon=True)
                thread.start()
                thread.join(timeout=2.0)  # Wait up to 2 seconds for send to complete
                
                frame_count[0] += 1
                
                # Schedule next frame
                if self.animation_running:
                    self.animation_timer = self.root.after(frame_delay, send_next_frame)
                
            except Exception as e:
                print(f"Animation error: {e}")
                self.stop_animation()
        
        # Start animation
        send_next_frame()
    
    def stop_animation(self):
        """Stop the running animation"""
        self.animation_running = False
        
        if self.animation_timer:
            self.root.after_cancel(self.animation_timer)
            self.animation_timer = None
        
        self.send_anim_btn.config(state=tk.NORMAL if self.is_connected else tk.DISABLED)
        self.stop_anim_btn.config(state=tk.DISABLED)
    
    def save_animation_preset(self):
        """Save animation configuration as preset"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Animation Preset")
        dialog.geometry("400x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Preset Name:").pack(pady=(20, 5))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=(0, 10))
        name_entry.insert(0, f"Animation - {self.anim_type_var.get().replace('_', ' ').title()}")
        name_entry.focus()
        name_entry.select_range(0, tk.END)
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("No Name", "Please enter a preset name")
                return
            
            preset = {
                "name": name,
                "type": "animation",
                "anim_type": self.anim_type_var.get(),
                "color_scheme": self.anim_color_scheme_var.get(),
                "speed": self.anim_speed_var.get(),
                "duration": self.anim_duration_var.get(),
                "gol_density": self.gol_density_var.get()
            }
            
            self.presets.append(preset)
            self.save_presets()
            self.refresh_preset_buttons()
            dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save).pack(pady=10)
    
    def create_teams_status_tab(self):
        """Create the Teams Status monitoring tab"""
        teams_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(teams_frame, text="Teams Status")
        
        teams_frame.columnconfigure(0, weight=1)
        
        # Info section
        info_frame = ttk.LabelFrame(teams_frame, text="ℹ️ About Teams Status", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        info_text = (
            "Automatically change your LED display based on your Microsoft Teams status!\n\n"
            "• Available = Green display\n"
            "• Busy / In a call = Red display\n"
            "• Away = Yellow display\n"
            "• Do Not Disturb = Purple display\n"
            "• Offline = Gray display\n\n"
            "You can map each status to a specific preset you've saved."
        )
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=750).pack()
        
        # Authentication section
        auth_frame = ttk.LabelFrame(teams_frame, text="🔐 Microsoft Authentication", padding="10")
        auth_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.teams_auth_status_var = tk.StringVar(value="Not authenticated")
        ttk.Label(auth_frame, textvariable=self.teams_auth_status_var, 
                 font=('TkDefaultFont', 9, 'italic')).grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        ttk.Button(auth_frame, text="🔑 Authenticate with Microsoft", 
                  command=self.authenticate_teams).grid(row=1, column=0, padx=(0, 5))
        ttk.Button(auth_frame, text="🔓 Sign Out", 
                  command=self.signout_teams).grid(row=1, column=1)
        
        # Status mapping section
        mapping_frame = ttk.LabelFrame(teams_frame, text="📋 Status → Preset Mapping", padding="10")
        mapping_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Get preset names for dropdown
        preset_names = ["(None)"] + [p["name"] for p in self.presets]
        
        statuses = [
            ("Available", "🟢", "teams_available_preset"),
            ("Busy", "🔴", "teams_busy_preset"),
            ("Do Not Disturb", "🟣", "teams_dnd_preset"),
            ("In a meeting", "🔴", "teams_meeting_preset"),
            ("Away", "🟡", "teams_away_preset"),
            ("Be Right Back", "🟡", "teams_brb_preset"),
            ("Offline", "⚫", "teams_offline_preset")
        ]
        
        self.teams_preset_vars = {}
        
        for idx, (status_name, emoji, var_name) in enumerate(statuses):
            ttk.Label(mapping_frame, text=f"{emoji} {status_name}:").grid(row=idx, column=0, sticky=tk.W, pady=2, padx=(0, 10))
            
            var = tk.StringVar(value=self.settings.get(var_name, "(None)"))
            self.teams_preset_vars[var_name] = var
            
            combo = ttk.Combobox(mapping_frame, textvariable=var, values=preset_names, 
                                state="readonly", width=40)
            combo.grid(row=idx, column=1, sticky=(tk.W, tk.E), pady=2)
            combo.bind('<<ComboboxSelected>>', lambda e, v=var_name: self.save_teams_mapping(v))
        
        mapping_frame.columnconfigure(1, weight=1)
        
        # Monitoring section  
        monitor_frame = ttk.LabelFrame(teams_frame, text="👁️ Status Monitoring", padding="10")
        monitor_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Current status display
        ttk.Label(monitor_frame, text="Current Status:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.teams_current_status_var = tk.StringVar(value="Unknown")
        ttk.Label(monitor_frame, textvariable=self.teams_current_status_var, 
             font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=1, sticky=tk.W)

        self.teams_debug_var = tk.StringVar(value="Debug: idle")
        ttk.Label(monitor_frame, textvariable=self.teams_debug_var,
             font=('TkDefaultFont', 8, 'italic'), foreground='gray').grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        
        # Refresh interval
        ttk.Label(monitor_frame, text="Check every:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.teams_refresh_var = tk.IntVar(value=self.settings.get('teams_refresh_interval', 30))
        interval_frame = ttk.Frame(monitor_frame)
        interval_frame.grid(row=2, column=1, sticky=tk.W, pady=(10, 0))
        ttk.Spinbox(interval_frame, from_=10, to=300, textvariable=self.teams_refresh_var, 
                   width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(interval_frame, text="seconds").pack(side=tk.LEFT)
        
        # Control buttons
        control_frame = ttk.Frame(monitor_frame)
        control_frame.grid(row=3, column=0, columnspan=2, pady=(15, 0))
        
        self.start_teams_btn = ttk.Button(control_frame, text="▶️ Start Monitoring", 
                                         command=self.start_teams_monitoring)
        self.start_teams_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_teams_btn = ttk.Button(control_frame, text="⏹️ Stop Monitoring", 
                                        command=self.stop_teams_monitoring, state=tk.DISABLED)
        self.stop_teams_btn.pack(side=tk.LEFT)
        
        # Status info
        self.teams_monitor_status_var = tk.StringVar(value="Monitoring: Not running")
        ttk.Label(monitor_frame, textvariable=self.teams_monitor_status_var, 
                 font=('TkDefaultFont', 9, 'italic'), foreground='gray').grid(row=4, column=0, columnspan=2, pady=(10, 0))
    
    def save_teams_mapping(self, setting_name):
        """Save Teams status to preset mapping"""
        value = self.teams_preset_vars[setting_name].get()
        self.settings[setting_name] = value
        self.save_settings()
    
    def authenticate_teams(self):
        """Authenticate with Microsoft Graph API for Teams presence"""
        messagebox.showinfo(
            "Microsoft Teams Authentication",
            "To access your Teams status, you need to:\n\n"
            "1. Register an app in Azure Active Directory\n"
            "2. Grant 'Presence.Read.All' (Application) permission\n"
            "3. Admin-consent the permission\n"
            "4. Get your Client ID and Tenant ID\n"
            "5. Provide a User ID or UPN (email) to monitor\n\n"
            "This requires a Microsoft 365 account.\n\n"
            "See the documentation for detailed setup instructions:\n"
            "https://docs.microsoft.com/graph/auth-v2-user"
        )
        
        # Simple dialog for entering credentials
        dialog = tk.Toplevel(self.root)
        dialog.title("Microsoft Graph API Setup")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Azure AD Application Details", font=('TkDefaultFont', 11, 'bold')).pack(pady=(15, 10))
        
        # Client ID
        ttk.Label(dialog, text="Client ID (Application ID):").pack(anchor=tk.W, padx=20, pady=(10, 0))
        client_id_entry = ttk.Entry(dialog, width=60)
        client_id_entry.pack(padx=20, pady=(0, 10))
        client_id_entry.insert(0, self.secrets.get('teams_client_id', ''))
        
        # Tenant ID
        ttk.Label(dialog, text="Tenant ID (Directory ID):").pack(anchor=tk.W, padx=20)
        tenant_id_entry = ttk.Entry(dialog, width=60)
        tenant_id_entry.pack(padx=20, pady=(0, 10))
        tenant_id_entry.insert(0, self.secrets.get('teams_tenant_id', ''))
        
        # Client Secret
        ttk.Label(dialog, text="Client Secret:").pack(anchor=tk.W, padx=20)
        secret_entry = ttk.Entry(dialog, width=60, show="*")
        secret_entry.pack(padx=20, pady=(0, 15))
        secret_entry.insert(0, self.secrets.get('teams_client_secret', ''))

        # User ID / UPN
        ttk.Label(dialog, text="User ID / UPN (email):").pack(anchor=tk.W, padx=20)
        user_id_entry = ttk.Entry(dialog, width=60)
        user_id_entry.pack(padx=20, pady=(0, 15))
        user_id_entry.insert(0, self.secrets.get('teams_user_id', ''))
        
        def save_credentials():
            client_id = client_id_entry.get().strip()
            tenant_id = tenant_id_entry.get().strip()
            client_secret = secret_entry.get().strip()
            user_id = user_id_entry.get().strip()
            
            if not all([client_id, tenant_id, client_secret, user_id]):
                messagebox.showwarning("Missing Info", "Please fill in all fields")
                return
            
            self.secrets['teams_client_id'] = client_id
            self.secrets['teams_tenant_id'] = tenant_id
            self.secrets['teams_client_secret'] = client_secret
            self.secrets['teams_user_id'] = user_id
            self.save_secrets()
            
            self.teams_auth_status_var.set("✓ Credentials saved. Ready to monitor!")
            dialog.destroy()
            messagebox.showinfo("Success", "Credentials saved! You can now start monitoring your Teams status.")
        
        ttk.Button(dialog, text="Save & Close", command=save_credentials).pack(pady=10)
    
    def signout_teams(self):
        """Sign out from Teams monitoring"""
        self.stop_teams_monitoring()
        self.secrets['teams_client_id'] = ''
        self.secrets['teams_tenant_id'] = ''
        self.secrets['teams_client_secret'] = ''
        self.secrets['teams_user_id'] = ''
        self.teams_access_token = None
        self.save_secrets()
        self.teams_auth_status_var.set("Not authenticated")
        messagebox.showinfo("Signed Out", "Microsoft Teams credentials have been removed.")
    
    def start_teams_monitoring(self):
        """Start monitoring Teams status"""
        # Check if authenticated
        if not all([
            self.secrets.get('teams_client_id'),
            self.secrets.get('teams_tenant_id'),
            self.secrets.get('teams_client_secret'),
            self.secrets.get('teams_user_id')
        ]):
            messagebox.showwarning("Not Authenticated", "Please authenticate with Microsoft first.")
            return
        
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to your LED panel first.")
            return
        
        self.teams_monitoring = True
        self.start_teams_btn.config(state=tk.DISABLED)
        self.stop_teams_btn.config(state=tk.NORMAL)
        self.teams_monitor_status_var.set("Monitoring: Running ✓")
        
        # Start checking status
        self.check_teams_status()
    
    def stop_teams_monitoring(self):
        """Stop monitoring Teams status"""
        self.teams_monitoring = False
        if self.teams_timer:
            self.root.after_cancel(self.teams_timer)
            self.teams_timer = None
        
        self.start_teams_btn.config(state=tk.NORMAL)
        self.stop_teams_btn.config(state=tk.DISABLED)
        self.teams_monitor_status_var.set("Monitoring: Stopped")
    
    def check_teams_status(self):
        """Check current Teams status via Microsoft Graph API"""
        if not self.teams_monitoring:
            return
        
        def fetch_status():
            try:
                user_id = self.secrets.get('teams_user_id', '').strip()
                if not user_id:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Missing User", "Please provide a Teams User ID or UPN in the Teams settings."
                    ))
                    self.root.after(0, self.stop_teams_monitoring)
                    return

                user_id_encoded = urllib.parse.quote(user_id, safe="")
                self.root.after(0, lambda: self.teams_debug_var.set("Debug: checking presence..."))

                # Get access token if needed
                if not self.teams_access_token:
                    token_response = self.get_teams_access_token()
                    if not token_response:
                        err = self.teams_last_error or "Authentication failed"
                        self.root.after(0, lambda e=err: self.teams_current_status_var.set(f"Error: {e}"))
                        self.root.after(0, lambda: messagebox.showerror(
                            "Authentication Failed", 
                            "Could not authenticate with Microsoft Graph API. Check your credentials."
                        ))
                        self.root.after(0, self.stop_teams_monitoring)
                        return
                    self.teams_access_token = token_response
                
                # Get user presence
                headers = {
                    'Authorization': f'Bearer {self.teams_access_token}',
                    'Content-Type': 'application/json'
                }
                
                # Use Graph API to get presence
                response = requests.get(
                    f'https://graph.microsoft.com/v1.0/users/{user_id_encoded}/presence',
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 401:
                    # Token expired, refresh it
                    self.teams_access_token = None
                    self.root.after(0, self.check_teams_status)
                    return
                
                if response.status_code == 200:
                    data = response.json()
                    availability = data.get('availability', 'Unknown')
                    activity = data.get('activity', 'Unknown')
                    self.teams_last_error = None
                    self.root.after(0, lambda: self.teams_debug_var.set("Debug: presence OK"))

                    status_display = availability if availability and availability != 'Unknown' else activity
                    status_display = status_display if status_display else 'Unknown'
                    
                    # Update UI with current status
                    self.root.after(0, lambda s=status_display, a=activity: self.teams_current_status_var.set(
                        f"{s} ({a})"
                    ))
                    
                    # Check if status changed
                    status_key = availability
                    if not status_key or status_key == 'Unknown':
                        status_key = activity

                    if status_key != self.teams_last_status:
                        self.teams_last_status = status_key
                        self.root.after(0, lambda s=status_key: self.handle_teams_status_change(s))
                else:
                    error_summary = f"{response.status_code} {response.reason}" if hasattr(response, 'reason') else f"{response.status_code}"
                    self.teams_last_error = f"Presence error: {error_summary}"
                    self.root.after(0, lambda e=self.teams_last_error: self.teams_current_status_var.set(f"Error: {e}"))
                    self.root.after(0, lambda e=self.teams_last_error: self.teams_debug_var.set(f"Debug: {e}"))
                    print(f"Teams API error: {response.status_code} - {response.text}")
                    
            except Exception as e:
                self.teams_last_error = f"Presence error: {e}"
                self.root.after(0, lambda e=self.teams_last_error: self.teams_current_status_var.set(f"Error: {e}"))
                self.root.after(0, lambda e=self.teams_last_error: self.teams_debug_var.set(f"Debug: {e}"))
                print(f"Error checking Teams status: {e}")
        
        # Run in background thread
        threading.Thread(target=fetch_status, daemon=True).start()
        
        # Schedule next check
        interval = self.teams_refresh_var.get() * 1000
        self.teams_timer = self.root.after(interval, self.check_teams_status)
    
    def get_teams_access_token(self):
        """Get access token from Microsoft Graph API"""
        try:
            import requests
            
            tenant_id = self.secrets.get('teams_tenant_id')
            client_id = self.secrets.get('teams_client_id')
            client_secret = self.secrets.get('teams_client_secret')
            
            # Using client credentials flow (requires admin consent)
            token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': 'https://graph.microsoft.com/.default'
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            
            if response.status_code == 200:
                self.teams_last_error = None
                self.root.after(0, lambda: self.teams_debug_var.set("Debug: token OK"))
                return response.json()['access_token']
            else:
                self.teams_last_error = f"Token error: {response.status_code}"
                self.root.after(0, lambda e=self.teams_last_error: self.teams_debug_var.set(f"Debug: {e}"))
                print(f"Token error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.teams_last_error = f"Token error: {e}"
            self.root.after(0, lambda e=self.teams_last_error: self.teams_debug_var.set(f"Debug: {e}"))
            print(f"Error getting access token: {e}")
            return None
    
    def handle_teams_status_change(self, status):
        """Handle Teams status change by activating corresponding preset"""
        # Map status to setting name
        status_mapping = {
            'Available': 'teams_available_preset',
            'Busy': 'teams_busy_preset',
            'DoNotDisturb': 'teams_dnd_preset',
            'InAMeeting': 'teams_meeting_preset',
            'Away': 'teams_away_preset',
            'BeRightBack': 'teams_brb_preset',
            'Offline': 'teams_offline_preset'
        }
        
        setting_name = status_mapping.get(status)
        if not setting_name:
            return
        
        preset_name = self.settings.get(setting_name)
        if not preset_name or preset_name == "(None)":
            return
        
        # Find and execute the preset
        for preset in self.presets:
            if preset['name'] == preset_name:
                self.execute_preset(preset)
                print(f"Teams status changed to {status}, executed preset: {preset_name}")
                break
    
    def create_settings_tab(self):
        """Create the settings control tab"""
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="Settings")

        settings_frame.columnconfigure(1, weight=1)
        
        # Brightness
        ttk.Label(settings_frame, text="Brightness:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        self.brightness_var = tk.IntVar(value=50)
        brightness_frame = ttk.Frame(settings_frame)
        brightness_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Scale(brightness_frame, from_=1, to=100, variable=self.brightness_var, orient=tk.HORIZONTAL, length=300).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(brightness_frame, textvariable=self.brightness_var).pack(side=tk.LEFT)
        
        self.set_brightness_btn = ttk.Button(settings_frame, text="Set Brightness", command=self.set_brightness, state=tk.DISABLED)
        self.set_brightness_btn.grid(row=1, column=0, columnspan=2, pady=(0, 20))

        # Power control
        ttk.Label(settings_frame, text="Power Control:").grid(row=2, column=0, sticky=tk.W, pady=(0, 10))
        
        power_frame = ttk.Frame(settings_frame)
        power_frame.grid(row=2, column=1, sticky=tk.W, pady=(0, 10))
        
        self.power_on_btn = ttk.Button(power_frame, text="Power ON", command=lambda: self.set_power(True), state=tk.DISABLED)
        self.power_on_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.power_off_btn = ttk.Button(power_frame, text="Power OFF", command=lambda: self.set_power(False), state=tk.DISABLED)
        self.power_off_btn.pack(side=tk.LEFT)

        # Sprite font library
        sprite_frame = ttk.LabelFrame(settings_frame, text="Sprite Fonts", padding="10")
        sprite_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        sprite_frame.columnconfigure(1, weight=1)

        self.sprite_font_listbox = tk.Listbox(sprite_frame, height=6)
        self.sprite_font_listbox.grid(row=0, column=0, rowspan=4, sticky=(tk.N, tk.S, tk.W))
        self.sprite_font_listbox.bind('<<ListboxSelect>>', self._on_sprite_font_select)

        list_scroll = ttk.Scrollbar(sprite_frame, orient=tk.VERTICAL, command=self.sprite_font_listbox.yview)
        list_scroll.grid(row=0, column=1, rowspan=4, sticky=(tk.N, tk.S))
        self.sprite_font_listbox.configure(yscrollcommand=list_scroll.set)

        form_frame = ttk.Frame(sprite_frame)
        form_frame.grid(row=0, column=2, rowspan=4, sticky=(tk.W, tk.E))
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.sprite_font_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.sprite_font_name_var, width=24).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(form_frame, text="Sprite Sheet:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.sprite_font_path_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.sprite_font_path_var, width=24).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        ttk.Button(form_frame, text="Browse", command=self._browse_sprite_font_file).grid(row=1, column=2, padx=(5, 0))

        ttk.Label(form_frame, text="Glyph order:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        self.sprite_font_order_var = tk.StringVar(value='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/ ')
        ttk.Entry(form_frame, textvariable=self.sprite_font_order_var, width=24).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(form_frame, text="Columns:").grid(row=3, column=0, sticky=tk.W)
        self.sprite_font_cols_var = tk.IntVar(value=71)
        ttk.Spinbox(form_frame, from_=1, to=64, textvariable=self.sprite_font_cols_var, width=6).grid(row=3, column=1, sticky=tk.W)

        btn_frame = ttk.Frame(sprite_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))
        ttk.Button(btn_frame, text="Add", command=self._add_sprite_font).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Update", command=self._update_sprite_font).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Delete", command=self._delete_sprite_font).pack(side=tk.LEFT)

        self._refresh_sprite_font_listbox()
        self._refresh_sprite_font_dropdowns()
        
    def start_event_loop(self):
        """Start asyncio event loop in a separate thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        
    def run_async(self, coro):
        """Run an async coroutine in the event loop"""
        if self.loop:
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future.result(timeout=30)
        
    def scan_devices(self):
        """Scan for Bluetooth LE devices"""
        self.scan_btn.config(state=tk.DISABLED, text="Scanning...")
        self.device_combo['values'] = []
        
        def scan_task():
            try:
                devices = self.run_async(self._scan_devices())
                
                # Update UI in main thread
                self.root.after(0, lambda: self._update_device_list(devices))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Scan Error", f"Failed to scan: {error_msg}"))
            finally:
                self.root.after(0, lambda: self.scan_btn.configure(state=tk.NORMAL, text="Scan"))
        
        threading.Thread(target=scan_task, daemon=True).start()
    
    async def _scan_devices(self):
        """Async method to scan for devices"""
        devices = await BleakScanner.discover(timeout=5.0)
        # Filter for LED devices
        ipixel_devices = {}
        for device in devices:
            if device.name and ("LED" in device.name or "BLE" in device.name or "iPixel" in device.name):
                ipixel_devices[f"{device.name} ({device.address})"] = device.address
        return ipixel_devices
    
    def _update_device_list(self, devices):
        """Update the device list in the UI"""
        if devices:
            self.device_combo['values'] = list(devices.keys())
            self.device_combo.current(0)
            self.devices_dict = devices
    
    def toggle_connection(self):
        """Connect or disconnect from device"""
        if not self.is_connected:
            self.connect_device()
        else:
            self.disconnect_device()
    
    def connect_device(self):
        """Connect to the selected device"""
        device_str = self.device_var.get()
        if not device_str:
            messagebox.showwarning("No Device", "Please scan and select a device first")
            return
        
        self.device_address = self.devices_dict.get(device_str)
        if not self.device_address:
            messagebox.showerror("Error", "Device address not found")
            return
        
        self.connect_btn.config(state=tk.DISABLED, text="Connecting...")
        
        def connect_task():
            try:
                # Create client - this may handle connection internally
                self.client = Client(self.device_address)
                
                # Try to connect if method exists and is callable
                if hasattr(self.client, 'connect') and callable(self.client.connect):
                    self.client.connect()
                
                # Update UI
                self.root.after(0, self._on_connected)
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._on_connection_error(error_msg))
        
        threading.Thread(target=connect_task, daemon=True).start()
    
    def _on_connected(self):
        """Called when successfully connected"""
        self.is_connected = True
        
        # Save device address for auto-connect
        self.settings['last_device'] = self.device_address
        self.save_settings()
        
        # Try to get device info
        device_info_text = "Connected"
        try:
            if hasattr(self.client, 'device_info') and self.client.device_info:
                info = self.client.device_info
                if hasattr(info, 'width') and hasattr(info, 'height'):
                    device_info_text = f"Connected - Resolution: {info.width}x{info.height}px"
        except:
            pass
        
        self.status_label.config(text=device_info_text, foreground="green")
        self.connect_btn.config(state=tk.NORMAL, text="Disconnect")
        
        # Enable control buttons
        self.send_text_btn.config(state=tk.NORMAL)
        self.send_image_btn.config(state=tk.NORMAL if self.image_path else tk.DISABLED)
        self.send_clock_btn.config(state=tk.NORMAL)
        self.set_brightness_btn.config(state=tk.NORMAL)
        self.power_on_btn.config(state=tk.NORMAL)
        self.power_off_btn.config(state=tk.NORMAL)
        
        # Enable new feature buttons
        if hasattr(self, 'send_stock_btn'):
            self.send_stock_btn.config(state=tk.NORMAL if hasattr(self, 'current_stock_data') and self.current_stock_data else tk.DISABLED)
        if hasattr(self, 'send_anim_btn'):
            self.send_anim_btn.config(state=tk.NORMAL)
    
    def _on_connection_error(self, error):
        """Called when connection fails"""
        self.connect_btn.config(state=tk.NORMAL, text="Connect")
        messagebox.showerror("Connection Error", f"Failed to connect: {error}")
    
    def disconnect_device(self):
        """Disconnect from the device"""
        if self.client:
            try:
                self.run_async(self.client.disconnect())
            except:
                pass
            
        self.is_connected = False
        self.client = None
        self.status_label.config(text="Disconnected", foreground="red")
        self.connect_btn.config(text="Connect")
        
        # Disable control buttons
        self.send_text_btn.config(state=tk.DISABLED)
        self.send_image_btn.config(state=tk.DISABLED)
        self.send_clock_btn.config(state=tk.DISABLED)
        self.set_brightness_btn.config(state=tk.DISABLED)
        self.power_on_btn.config(state=tk.DISABLED)
        self.power_off_btn.config(state=tk.DISABLED)
        
        # Disable new feature buttons
        if hasattr(self, 'send_stock_btn'):
            self.send_stock_btn.config(state=tk.DISABLED)
        if hasattr(self, 'send_youtube_btn'):
            self.send_youtube_btn.config(state=tk.DISABLED)
        if hasattr(self, 'send_weather_btn'):
            self.send_weather_btn.config(state=tk.DISABLED)
        if hasattr(self, 'send_anim_btn'):
            self.send_anim_btn.config(state=tk.DISABLED)
            self.stop_anim_btn.config(state=tk.DISABLED)
    
    def choose_text_color(self):
        """Choose text color"""
        color = colorchooser.askcolor(initialcolor=self.text_color)
        if color[1]:
            self.text_color = color[1]
            self.text_color_canvas.config(bg=self.text_color)
    
    def choose_bg_color(self):
        """Choose background color"""
        color = colorchooser.askcolor(initialcolor=self.bg_color)
        if color[1]:
            self.bg_color = color[1]
            self.bg_color_canvas.config(bg=self.bg_color)
    
    def send_text(self):
        """Send text to the display"""
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "Please enter text to display")
            return

        self._stop_active_display_tasks()
        
        # Clear last preset to prevent auto-restore from overriding manual text
        self.settings['last_preset'] = None
        self.save_settings()
        
        self.send_text_btn.config(state=tk.DISABLED, text="Sending...")
        
        def send_text_value(value_text, anim_override=None):
            def send_task():
                try:
                    anim = anim_override if anim_override is not None else self.animation_var.get()
                    if self.text_use_sprite_var.get():
                        font = self._get_sprite_font_by_name(self.text_sprite_font_var.get().strip())
                        if not font:
                            raise Exception("Sprite font not found")
                        if anim in (1, 2):
                            line_img, sprite_err = self._build_sprite_text_line_image(
                                value_text,
                                font.get('path', ''),
                                font.get('order', ''),
                                font.get('cols', 1),
                                self.bg_color
                            )
                            if line_img is None:
                                raise Exception(sprite_err or "Sprite render failed")
                            direction = "right" if anim == 2 else "left"
                            self._start_sprite_scroll(line_img, self.bg_color, self.speed_var.get(), direction=direction)
                            return
                        sprite_img, sprite_err = self._build_sprite_text_image(
                            value_text,
                            font.get('path', ''),
                            font.get('order', ''),
                            font.get('cols', 1),
                            self.bg_color
                        )
                        if sprite_img is None:
                            raise Exception(sprite_err or "Sprite render failed")

                        tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_text_sprite.png')
                        sprite_img.save(tmp_path, 'PNG')
                        result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                        if asyncio.iscoroutine(result):
                            self.run_async(result)
                    else:
                        text_color_hex = self.text_color.lstrip('#')
                        bg_color_hex = self.bg_color.lstrip('#')
                        inverted_speed = 101 - self.speed_var.get()
                        result = self.client.send_text(
                            value_text,
                            char_height=16,
                            color=text_color_hex,
                            bg_color=bg_color_hex,
                            animation=anim,
                            speed=inverted_speed,
                            rainbow_mode=self.rainbow_var.get()
                        )
                        if asyncio.iscoroutine(result):
                            self.run_async(result)
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send text: {error_msg}"))
                finally:
                    self.root.after(0, lambda: self.send_text_btn.config(state=tk.NORMAL, text="Send Text"))

            threading.Thread(target=send_task, daemon=True).start()

        if self.animation_var.get() == 0:
            parts = [p.strip() for p in text.replace('|', '\n').splitlines() if p.strip()]

            if self.text_use_sprite_var.get():
                font = self._get_sprite_font_by_name(self.text_sprite_font_var.get().strip())
                if not font:
                    messagebox.showerror("Error", "Sprite font not found")
                    return

                try:
                    sprite = Image.open(font.get('path', '')).convert("RGBA")
                    cols = max(1, int(font.get('cols', 1)))
                    tile_w = max(1, sprite.width // cols)
                except Exception as e:
                    messagebox.showerror("Error", f"Sprite load failed: {e}")
                    return

                max_chars = max(1, 64 // tile_w)
                delay_ms = max(1, int(self.text_static_delay_var.get() or 2)) * 1000

                pages = []
                for segment in (parts if parts else [text]):
                    words = segment.split()
                    current = ""
                    for word in words:
                        if not word:
                            continue
                        if len(word) > max_chars:
                            if current:
                                pages.append({"text": current, "scroll": False})
                                current = ""
                            pages.append({"text": word, "scroll": True})
                            continue

                        candidate = word if not current else f"{current} {word}"
                        if len(candidate) <= max_chars:
                            current = candidate
                        else:
                            if current:
                                pages.append({"text": current, "scroll": False})
                            current = word

                    if current:
                        pages.append({"text": current, "scroll": False})

                if not pages:
                    return

                state = {'idx': 0}

                def show_page():
                    page = pages[state['idx']]
                    value_text = page['text']
                    try:
                        self._stop_sprite_scroll()
                        if page['scroll']:
                            line_img, sprite_err = self._build_sprite_text_line_image(
                                value_text,
                                font.get('path', ''),
                                font.get('order', ''),
                                font.get('cols', 1),
                                self.bg_color
                            )
                            if line_img is None:
                                raise Exception(sprite_err or "Sprite render failed")
                            if line_img.width <= 64:
                                send_text_value(value_text, anim_override=0)
                                next_delay = delay_ms
                            else:
                                self._start_sprite_scroll(line_img, self.bg_color, self.speed_var.get(), direction="left")
                                end_pad = 8
                                scroll_width = line_img.width + end_pad
                                max_offset = max(0, scroll_width - 64)
                                interval = self._sprite_scroll_interval_ms(self.speed_var.get())
                                scroll_duration = (max_offset + 1) * interval + 3000
                                next_delay = scroll_duration + delay_ms
                        else:
                            send_text_value(value_text, anim_override=0)
                            next_delay = delay_ms

                        def advance():
                            self._stop_sprite_scroll()
                            state['idx'] = (state['idx'] + 1) % len(pages)
                            show_page()

                        self.text_static_timer = self.root.after(next_delay, advance)
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send text: {error_msg}"))

                show_page()
                return

            if len(parts) > 1:
                delay_ms = max(1, int(self.text_static_delay_var.get() or 2)) * 1000
                state = {'idx': 0}

                def tick():
                    send_text_value(parts[state['idx']], anim_override=0)
                    state['idx'] = (state['idx'] + 1) % len(parts)
                    self.text_static_timer = self.root.after(delay_ms, tick)

                tick()
                return

        send_text_value(text)
    
    def load_image(self):
        """Load an image file"""
        filepath = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            try:
                # Load and show preview
                img = Image.open(filepath)
                img.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(img)
                
                self.image_preview_label.config(image=photo, text="")
                self.image_preview_label.image = photo  # Keep a reference
                
                self.image_path = filepath
                self.send_image_btn.config(state=tk.NORMAL if self.is_connected else tk.DISABLED)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {str(e)}")
    
    def send_image(self):
        """Send image to the display"""
        if not self.image_path:
            messagebox.showwarning("No Image", "Please load an image first")
            return

        image_path = self._resolve_asset_path(self.image_path)
        if not os.path.exists(image_path):
            messagebox.showwarning("Missing Image", f"Image not found: {image_path}")
            return
        
        self._stop_active_display_tasks()
        
        # Clear last preset to prevent auto-restore from overriding manual image
        self.settings['last_preset'] = None
        self.save_settings()
        
        self.send_image_btn.config(state=tk.DISABLED, text="Sending...")
        
        def send_task():
            try:
                # First, clear any existing display mode
                try:
                    clear_result = self.client.clear()
                    if asyncio.iscoroutine(clear_result):
                        self.run_async(clear_result)
                except:
                    pass  # Clear might not be available
                
                # Send image with save_slot=0 to display immediately
                # Using 'crop' resize method to fill the entire display
                result = self.client.send_image(image_path, resize_method='crop', save_slot=0)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send image: {error_msg}"))
            finally:
                self.root.after(0, lambda: self.send_image_btn.config(state=tk.NORMAL, text="Send Image"))
        
        threading.Thread(target=send_task, daemon=True).start()
    
    def update_clock_options(self):
        """Update visibility of clock options based on selected mode"""
        mode = self.clock_mode_var.get()
        
        if mode == "builtin":
            self.builtin_frame.pack(fill=tk.X, pady=(0, 10))
            self.custom_frame.pack_forget()
            self.countdown_frame.pack_forget()
            self.stop_clock_btn.config(state=tk.DISABLED)
        elif mode == "custom":
            self.builtin_frame.pack_forget()
            self.custom_frame.pack(fill=tk.X, pady=(0, 10))
            self.countdown_frame.pack_forget()
        else:  # countdown
            self.builtin_frame.pack_forget()
            self.custom_frame.pack_forget()
            self.countdown_frame.pack(fill=tk.X, pady=(0, 10))
    
    def choose_clock_color(self):
        """Choose clock text color"""
        color = colorchooser.askcolor(title="Choose Clock Text Color", initialcolor=self.clock_color)
        if color[1]:
            self.clock_color = color[1]
            self.clock_color_canvas.config(bg=self.clock_color)
    
    def choose_clock_bg_color(self):
        """Choose clock background color"""
        color = colorchooser.askcolor(title="Choose Clock Background Color", initialcolor=self.clock_bg_color)
        if color[1]:
            self.clock_bg_color = color[1]
            self.clock_bg_color_canvas.config(bg=self.clock_bg_color)

    def _get_sprite_fonts(self):
        return self.settings.get('sprite_fonts', []) or []

    def _ensure_default_sprite_fonts(self):
        defaults = [
            {
                'name': 'Text Default',
                'path': os.path.join('Gallery', 'Sprites', 'TextSprite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text Long',
                'path': os.path.join('Gallery', 'Sprites', 'Text-Long-Sprite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text Long White',
                'path': os.path.join('Gallery', 'Sprites', 'Text-Long-White-Sprite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text Long Yellow',
                'path': os.path.join('Gallery', 'Sprites', 'Text-Long-Yellow-Sprite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text Thin',
                'path': os.path.join('Gallery', 'Sprites', 'Text-thin-Sprite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text Thin White',
                'path': os.path.join('Gallery', 'Sprites', 'Text-thin-White-Sprite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text Thin Yellow',
                'path': os.path.join('Gallery', 'Sprites', 'Text-thin-Yellow-Sprite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text White',
                'path': os.path.join('Gallery', 'Sprites', 'TextSpriteWhite.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Text Yellow',
                'path': os.path.join('Gallery', 'Sprites', 'TextSpriteYellow.png'),
                'order': '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%',
                'cols': 73
            },
            {
                'name': 'Clock Default',
                'path': os.path.join('Gallery', 'Sprites', 'SmallerClocksSprite-transp.png'),
                'order': '0123456789:',
                'cols': 11
            }
        ]

        fonts = self._get_sprite_fonts()
        existing = {f.get('name') for f in fonts if f.get('name')}
        added = False

        for entry in defaults:
            if entry['name'] not in existing:
                fonts.append(entry)
                added = True

        if added:
            self.settings['sprite_fonts'] = fonts
            self.save_settings()

    def _get_sprite_font_names(self):
        return [f.get('name', '') for f in self._get_sprite_fonts() if f.get('name')]

    def _get_sprite_font_by_name(self, name):
        for font in self._get_sprite_fonts():
            if font.get('name') == name:
                return font
        return None

    def _refresh_sprite_font_dropdowns(self):
        names = self._get_sprite_font_names()
        for combo_attr in [
            'text_sprite_font_combo',
            'clock_sprite_font_combo',
            'countdown_sprite_font_combo',
            'stock_sprite_font_combo',
            'youtube_sprite_font_combo'
        ]:
            combo = getattr(self, combo_attr, None)
            if combo:
                combo['values'] = names

    def _refresh_sprite_font_listbox(self):
        if not hasattr(self, 'sprite_font_listbox'):
            return
        self.sprite_font_listbox.delete(0, tk.END)
        for font in self._get_sprite_fonts():
            self.sprite_font_listbox.insert(tk.END, font.get('name', ''))

    def _on_sprite_font_select(self, event=None):
        if not hasattr(self, 'sprite_font_listbox'):
            return
        selection = self.sprite_font_listbox.curselection()
        if not selection:
            return
        name = self.sprite_font_listbox.get(selection[0])
        font = self._get_sprite_font_by_name(name)
        if not font:
            return
        self.sprite_font_name_var.set(font.get('name', ''))
        self.sprite_font_path_var.set(font.get('path', ''))
        self.sprite_font_order_var.set(font.get('order', ''))
        self.sprite_font_cols_var.set(font.get('cols', 1))

    def _browse_sprite_font_file(self):
        filepath = filedialog.askopenfilename(
            title="Select sprite sheet",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        if filepath:
            self.sprite_font_path_var.set(filepath)

    def _add_sprite_font(self):
        name = self.sprite_font_name_var.get().strip()
        path = self.sprite_font_path_var.get().strip()
        order = self.sprite_font_order_var.get().strip() or '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/ '
        cols = int(self.sprite_font_cols_var.get() or 1)
        if not name or not path:
            messagebox.showwarning("Missing Data", "Please provide a name and sprite sheet path.")
            return
        if self._get_sprite_font_by_name(name):
            messagebox.showwarning("Duplicate Name", "A sprite font with this name already exists.")
            return
        fonts = self._get_sprite_fonts()
        fonts.append({'name': name, 'path': path, 'order': order, 'cols': cols})
        self.settings['sprite_fonts'] = fonts
        self.save_settings()
        self._refresh_sprite_font_listbox()
        self._refresh_sprite_font_dropdowns()

    def _update_sprite_font(self):
        name = self.sprite_font_name_var.get().strip()
        path = self.sprite_font_path_var.get().strip()
        order = self.sprite_font_order_var.get().strip() or '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/ '
        cols = int(self.sprite_font_cols_var.get() or 1)
        if not name or not path:
            messagebox.showwarning("Missing Data", "Please provide a name and sprite sheet path.")
            return
        fonts = self._get_sprite_fonts()
        updated = False
        for font in fonts:
            if font.get('name') == name:
                font.update({'path': path, 'order': order, 'cols': cols})
                updated = True
                break
        if not updated:
            fonts.append({'name': name, 'path': path, 'order': order, 'cols': cols})
        self.settings['sprite_fonts'] = fonts
        self.save_settings()
        self._refresh_sprite_font_listbox()
        self._refresh_sprite_font_dropdowns()

    def _delete_sprite_font(self):
        name = self.sprite_font_name_var.get().strip()
        if not name:
            return
        fonts = [f for f in self._get_sprite_fonts() if f.get('name') != name]
        self.settings['sprite_fonts'] = fonts
        self.save_settings()
        self._refresh_sprite_font_listbox()
        self._refresh_sprite_font_dropdowns()

    def update_text_sprite_settings(self):
        """Persist sprite font settings for text"""
        self.settings['text_use_sprite_font'] = self.text_use_sprite_var.get()
        self.settings['text_sprite_font_name'] = self.text_sprite_font_var.get().strip()
        self.settings['text_static_delay_seconds'] = int(self.text_static_delay_var.get() or 2)
        self.save_settings()

    def update_clock_sprite_settings(self):
        """Persist sprite font settings for clock"""
        self.settings['clock_use_time_sprite'] = self.clock_use_time_sprite_var.get()
        self.settings['clock_time_sprite_font_name'] = self.clock_sprite_font_var.get().strip()
        self.save_settings()

    def update_countdown_sprite_settings(self):
        """Persist sprite font settings for countdown"""
        self.settings['countdown_use_sprite_font'] = self.countdown_use_sprite_var.get()
        self.settings['countdown_sprite_font_name'] = self.countdown_sprite_font_var.get().strip()
        self.settings['countdown_static_delay_seconds'] = int(self.countdown_static_delay_var.get() or 2)
        self.save_settings()

    def update_stock_sprite_settings(self):
        """Persist sprite font settings for stocks"""
        self.settings['stock_use_sprite_font'] = True
        self.settings['stock_sprite_font_name'] = self.stock_sprite_font_var.get().strip()
        self.settings['stock_static_delay_seconds'] = int(self.stock_static_delay_var.get() or 2)
        self.save_settings()

    def update_youtube_sprite_settings(self):
        """Persist sprite font settings for YouTube"""
        self.settings['youtube_use_sprite_font'] = self.youtube_use_sprite_var.get()
        self.settings['youtube_sprite_font_name'] = self.youtube_sprite_font_var.get().strip()
        self.save_settings()

    def browse_youtube_logo(self):
        filepath = filedialog.askopenfilename(
            title="Select YouTube logo (PNG)",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        if filepath:
            self.youtube_logo_path_var.set(filepath)
            self.update_youtube_logo_settings()

    def update_youtube_logo_settings(self):
        """Persist YouTube logo settings"""
        self.settings['youtube_show_logo'] = self.youtube_show_logo_var.get()
        self.settings['youtube_logo_path'] = self.youtube_logo_path_var.get().strip()
        self.save_settings()

    def _sprite_scroll_interval_ms(self, speed_value):
        try:
            speed = int(speed_value)
        except Exception:
            speed = 50
        return max(20, 220 - speed * 2)

    def _resolve_asset_path(self, path_value):
        if not path_value:
            return ""
        path_value = os.path.expanduser(path_value)
        if os.path.isabs(path_value):
            return path_value
        return os.path.normpath(os.path.join(os.path.dirname(__file__), path_value))

    def _build_sprite_text_line_image(self, text, sprite_path, order, cols, bg_color):
        """Build a single-line image from a sprite sheet without scaling to 64x16."""
        sprite_path = self._resolve_asset_path(sprite_path)
        if not sprite_path or not os.path.isfile(sprite_path):
            return None, "Sprite sheet not found"

        order = (order or "").strip()
        if not order:
            return None, "Glyph order is empty"

        try:
            cols = int(cols)
        except Exception:
            cols = 1
        cols = max(1, cols)

        try:
            sprite = Image.open(sprite_path).convert("RGBA")
        except Exception as e:
            return None, f"Sprite load failed: {e}"

        rows = max(1, math.ceil(len(order) / cols))
        tile_w = max(1, sprite.width // cols)
        tile_h = max(1, sprite.height // rows)

        glyphs = {}
        for idx, ch in enumerate(order):
            row = idx // cols
            col = idx % cols
            left = col * tile_w
            upper = row * tile_h
            right = left + tile_w
            lower = upper + tile_h
            if right <= sprite.width and lower <= sprite.height:
                glyphs[ch] = sprite.crop((left, upper, right, lower))

        if not glyphs:
            return None, "No glyphs found in sprite sheet"

        chars = list(text)
        total_w = tile_w * len(chars)
        base = Image.new("RGBA", (max(1, total_w), tile_h), bg_color)

        x = 0
        for ch in chars:
            glyph = glyphs.get(ch)
            if glyph is None:
                glyph = glyphs.get(ch.upper())
            if glyph is None and ch == " ":
                x += tile_w
                continue
            if glyph is None:
                x += tile_w
                continue
            base.paste(glyph, (x, 0), glyph)
            x += tile_w

        return base.convert("RGB"), None

    def _stop_sprite_scroll(self):
        self.sprite_scroll_running = False
        if self.sprite_scroll_timer:
            self.root.after_cancel(self.sprite_scroll_timer)
            self.sprite_scroll_timer = None

    def _start_sprite_scroll(self, line_img, bg_color, speed, direction="left"):
        self._stop_sprite_scroll()
        self.sprite_scroll_running = True

        end_pad = 8
        if end_pad > 0 and line_img.width > 0:
            if direction == "left":
                padded = Image.new(line_img.mode, (line_img.width + end_pad, line_img.height), bg_color)
                padded.paste(line_img, (0, 0))
                line_img = padded
            elif direction == "right":
                padded = Image.new(line_img.mode, (line_img.width + end_pad, line_img.height), bg_color)
                padded.paste(line_img, (end_pad, 0))
                line_img = padded

        if line_img.width <= 64:
            frame = line_img
            if line_img.height != 16:
                frame = line_img.resize((64, 16), Image.NEAREST)
            tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_sprite_scroll.png')
            frame.save(tmp_path, 'PNG')
            result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
            if asyncio.iscoroutine(result):
                self.run_async(result)
            self._stop_sprite_scroll()
            return

        max_offset = line_img.width - 64
        offset = [max_offset if direction == "right" else 0]
        step = -1 if direction == "right" else 1
        interval = self._sprite_scroll_interval_ms(speed)
        pause_ms = 3000

        def tick():
            if not self.sprite_scroll_running:
                return

            try:
                crop = line_img.crop((offset[0], 0, offset[0] + 64, line_img.height))
                if line_img.height != 16:
                    crop = crop.resize((64, 16), Image.NEAREST)
                tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_sprite_scroll.png')
                crop.save(tmp_path, 'PNG')
                result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
            except Exception:
                pass

            next_offset = offset[0] + step
            wrapped = False
            if next_offset > max_offset:
                next_offset = 0
                wrapped = True
            elif next_offset < 0:
                next_offset = max_offset
                wrapped = True

            offset[0] = next_offset
            if self.sprite_scroll_running:
                delay = pause_ms if wrapped else interval
                self.sprite_scroll_timer = self.root.after(delay, tick)

        self.sprite_scroll_timer = self.root.after(interval, tick)

    def _build_sprite_text_image(self, text, sprite_path, order, cols, bg_color):
        """Build a 64x16 image from a sprite sheet and text."""
        sprite_path = self._resolve_asset_path(sprite_path)
        if not sprite_path or not os.path.isfile(sprite_path):
            return None, "Sprite sheet not found"

        order = (order or "").strip()
        if not order:
            return None, "Glyph order is empty"

        try:
            cols = int(cols)
        except Exception:
            cols = 1
        cols = max(1, cols)

        try:
            sprite = Image.open(sprite_path).convert("RGBA")
        except Exception as e:
            return None, f"Sprite load failed: {e}"

        rows = max(1, math.ceil(len(order) / cols))
        tile_w = max(1, sprite.width // cols)
        tile_h = max(1, sprite.height // rows)

        glyphs = {}
        for idx, ch in enumerate(order):
            row = idx // cols
            col = idx % cols
            left = col * tile_w
            upper = row * tile_h
            right = left + tile_w
            lower = upper + tile_h
            if right <= sprite.width and lower <= sprite.height:
                glyphs[ch] = sprite.crop((left, upper, right, lower))

        if not glyphs:
            return None, "No glyphs found in sprite sheet"

        chars = list(text)
        total_w = tile_w * len(chars)
        base = Image.new("RGBA", (max(1, total_w), tile_h), bg_color)

        x = 0
        for ch in chars:
            glyph = glyphs.get(ch)
            if glyph is None:
                glyph = glyphs.get(ch.upper())
            if glyph is None and ch == " ":
                x += tile_w
                continue
            if glyph is None:
                x += tile_w
                continue
            base.paste(glyph, (x, 0), glyph)
            x += tile_w

        target_w, target_h = 64, 16
        if base.size != (target_w, target_h):
            scale = min(target_w / base.width, target_h / base.height)
            new_w = max(1, int(base.width * scale))
            new_h = max(1, int(base.height * scale))
            resized = base.resize((new_w, new_h), Image.NEAREST)
            canvas = Image.new("RGBA", (target_w, target_h), bg_color)
            offset_x = (target_w - new_w) // 2
            offset_y = (target_h - new_h) // 2
            canvas.paste(resized, (offset_x, offset_y), resized)
            base = canvas

        return base.convert("RGB"), None

    def _build_time_sprite_image(self, time_text):
        """Build a 64x16 clock image from a sprite sheet."""
        font_name = self.clock_sprite_font_var.get().strip()
        font = self._get_sprite_font_by_name(font_name)
        if not font:
            return None, "Sprite font not found"
        return self._build_sprite_text_image(
            time_text,
            font.get('path', ''),
            font.get('order', '0123456789:'),
            font.get('cols', 1),
            self.clock_bg_color
        )

    
    def choose_countdown_color(self):
        """Choose countdown text color"""
        color = colorchooser.askcolor(title="Choose Countdown Text Color", initialcolor=self.countdown_color)
        if color[1]:
            self.countdown_color = color[1]
            self.countdown_color_canvas.config(bg=self.countdown_color)
    
    def choose_countdown_bg_color(self):
        """Choose countdown background color"""
        color = colorchooser.askcolor(title="Choose Countdown Background Color", initialcolor=self.countdown_bg_color)
        if color[1]:
            self.countdown_bg_color = color[1]
            self.countdown_bg_color_canvas.config(bg=self.countdown_bg_color)
    
    def show_clock(self):
        """Show clock on the display"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Connect to device first")
            return
        
        # Clear last preset to prevent auto-restore from overriding manual clock
        self.settings['last_preset'] = None
        self.save_settings()
        
        mode = self.clock_mode_var.get()
        
        if mode == "builtin":
            # Use built-in hardware clock
            self.send_clock_btn.config(state=tk.DISABLED, text="Sending...")
            
            def send_task():
                try:
                    result = self.client.set_clock_mode(style=self.clock_style_var.get())
                    if asyncio.iscoroutine(result):
                        self.run_async(result)
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to show clock: {error_msg}"))
                finally:
                    self.root.after(0, lambda: self.send_clock_btn.config(state=tk.NORMAL, text="Show Clock"))
            
            threading.Thread(target=send_task, daemon=True).start()
        elif mode == "custom":
            # Start custom live clock
            if hasattr(self, 'clock_image_status_var'):
                self.clock_image_status_var.set("Starting live clock...")
            self.start_live_clock()
        else:  # countdown
            # Start countdown timer
            self.start_countdown()
    
    def start_live_clock(self):
        """Start a live updating custom clock"""
        import time
        
        # Stop any existing clock
        self.stop_live_clock()
        self._stop_sprite_scroll()
        if self.countdown_static_timer:
            self.root.after_cancel(self.countdown_static_timer)
            self.countdown_static_timer = None
        self._stop_sprite_scroll()
        
        # Stop any running stock auto-refresh
        self.stop_stock_refresh()
        
        self.send_clock_btn.config(state=tk.DISABLED)
        self.stop_clock_btn.config(state=tk.NORMAL)
        
        # Mark clock as running
        self.clock_running = True
        
        def update_time():
            if not self.clock_running:
                return  # Clock was stopped
            
            try:
                # Get current time
                current_time = time.strftime(self.time_format_var.get())
                
                # Determine animation
                animation = self.clock_animation_var.get()
                anim_map = {
                    "static": 0,
                    "scroll_left": 1,
                    "flash": 4
                }
                
                # Send text with current time
                def send_task():
                    try:
                        self.root.after(0, lambda t=current_time: self.clock_image_status_var.set(f"Clock tick: {t}"))

                        # Optional: use sprite sheet
                        if self.clock_use_time_sprite_var.get():
                            sprite_img, sprite_err = self._build_time_sprite_image(current_time)
                            if sprite_img is not None:
                                tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_clock_sprite.png')
                                sprite_img.save(tmp_path, 'PNG')
                                self.root.after(0, lambda p=tmp_path: self.clock_image_status_var.set(f"Sprite image: {os.path.basename(p)}"))
                                try:
                                    result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                    if asyncio.iscoroutine(result):
                                        self.run_async(result)
                                    return
                                except Exception as e:
                                    self.root.after(0, lambda: self.clock_image_status_var.set(f"Sprite send failed: {e}"))
                            else:
                                self.root.after(0, lambda: self.clock_image_status_var.set(f"Sprite error: {sprite_err} (fallback to images/text)"))

                        if not self.clock_use_time_sprite_var.get():
                            self.root.after(0, lambda: self.clock_image_status_var.set("Sprite sheet disabled"))

                        # Remove # from hex colors
                        color_hex = self.clock_color.lstrip('#')
                        bg_color_hex = self.clock_bg_color.lstrip('#')

                        result = self.client.send_text(
                            text=current_time,
                            char_height=16,
                            color=color_hex,
                            bg_color=bg_color_hex,
                            animation=anim_map.get(animation, 0),
                            speed=50
                        )

                        if asyncio.iscoroutine(result):
                            self.run_async(result)
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Clock update failed: {error_msg}"))
                        self.root.after(0, self.stop_live_clock)
                
                threading.Thread(target=send_task, daemon=True).start()
                
                # Schedule next update
                if self.clock_running:
                    interval = self.clock_update_interval_var.get() * 1000  # Convert to milliseconds
                    self.clock_timer = self.root.after(interval, update_time)
            except Exception as e:
                messagebox.showerror("Error", f"Clock error: {str(e)}")
                self.stop_live_clock()

        # Start the update loop
        update_time()
    
    def stop_live_clock(self):
        """Stop the live clock updates"""
        self.clock_running = False
        
        if self.clock_timer:
            self.root.after_cancel(self.clock_timer)
            self.clock_timer = None

        if self.countdown_static_timer:
            self.root.after_cancel(self.countdown_static_timer)
            self.countdown_static_timer = None

        self._stop_sprite_scroll()
        
        self.send_clock_btn.config(state=tk.NORMAL)
        self.stop_clock_btn.config(state=tk.DISABLED)
    
    def stop_stock_refresh(self):
        """Stop stock auto-refresh"""
        if self.stock_refresh_timer:
            self.root.after_cancel(self.stock_refresh_timer)
            self.stock_refresh_timer = None
        if self.stock_static_timer:
            self.root.after_cancel(self.stock_static_timer)
            self.stock_static_timer = None

    def _stop_active_display_tasks(self):
        if hasattr(self, 'clock_running') and self.clock_running:
            self.stop_live_clock()

        if self.animation_running:
            self.stop_animation()

        self._stop_sprite_scroll()

        if self.text_static_timer:
            self.root.after_cancel(self.text_static_timer)
            self.text_static_timer = None

        if self.countdown_static_timer:
            self.root.after_cancel(self.countdown_static_timer)
            self.countdown_static_timer = None

        if self.youtube_refresh_job:
            self.root.after_cancel(self.youtube_refresh_job)
            self.youtube_refresh_job = None

        if self.weather_refresh_job:
            self.root.after_cancel(self.weather_refresh_job)
            self.weather_refresh_job = None

        self.stop_stock_refresh()
    
    def start_countdown(self):
        """Start a countdown timer"""
        from datetime import datetime, timedelta
        
        # Stop any existing clock
        self.stop_live_clock()
        self._stop_sprite_scroll()
        if self.countdown_static_timer:
            self.root.after_cancel(self.countdown_static_timer)
            self.countdown_static_timer = None
        
        self.send_clock_btn.config(state=tk.DISABLED)
        self.stop_clock_btn.config(state=tk.NORMAL)
        
        # Mark clock as running
        self.clock_running = True
        
        # Get target date/time
        try:
            target_datetime = datetime(
                year=self.countdown_year_var.get(),
                month=self.countdown_month_var.get(),
                day=self.countdown_day_var.get(),
                hour=self.countdown_hour_var.get(),
                minute=self.countdown_minute_var.get()
            )
        except ValueError as e:
            messagebox.showerror("Invalid Date", f"Please enter a valid date and time: {str(e)}")
            self.stop_live_clock()
            return
        
        def update_countdown():
            if not self.clock_running:
                return
            
            try:
                now = datetime.now()
                
                # Format based on selection
                format_choice = self.countdown_format_var.get()

                event_name = self.countdown_event_var.get()

                # Check if event has passed
                if now >= target_datetime:
                    if format_choice == "with_name":
                        countdown_text = f"{event_name}: NOW!"
                    else:
                        countdown_text = "NOW!"
                else:
                    # Calculate time difference
                    delta = target_datetime - now
                    
                    days = delta.days
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if format_choice == "days_hours_mins":
                        countdown_text = f"{days}d {hours}h {minutes}m"
                    elif format_choice == "days_hours":
                        countdown_text = f"{days}d {hours}h"
                    elif format_choice == "hours_mins":
                        total_hours = days * 24 + hours
                        countdown_text = f"{total_hours}h {minutes}m"
                    elif format_choice == "days_only":
                        countdown_text = f"{days} days"
                    elif format_choice == "with_name":
                        countdown_text = f"{event_name}: {days}d {hours}h {minutes}m"
                    else:
                        countdown_text = f"{days}d {hours}h {minutes}m"

                def _build_countdown_frames():
                    if now >= target_datetime:
                        if format_choice == "with_name":
                            return [event_name.strip() or "Event", "NOW!"]
                        return ["NOW!"]

                    if format_choice == "with_name":
                        return [
                            event_name.strip() or "Event",
                            f"{days}d",
                            f"{hours}h {minutes}m"
                        ]
                    if format_choice == "days_hours_mins":
                        return [f"{days}d", f"{hours}h {minutes}m"]
                    if format_choice == "days_hours":
                        return [f"{days}d", f"{hours}h"]
                    if format_choice == "hours_mins":
                        total_hours = days * 24 + hours
                        return [f"{total_hours}h", f"{minutes}m"]
                    if format_choice == "days_only":
                        return [f"{days} days"]
                    return [f"{days}d", f"{hours}h {minutes}m"]
                
                # Determine animation
                animation = self.countdown_animation_var.get()
                anim_map = {
                    "static": 0,
                    "scroll_left": 1,
                    "flash": 4
                }
                if animation != "static" and self.countdown_static_timer:
                    self.root.after_cancel(self.countdown_static_timer)
                    self.countdown_static_timer = None
                if animation != "scroll_left":
                    self._stop_sprite_scroll()
                
                # Send text with countdown
                def send_task():
                    try:
                        if self.countdown_use_sprite_var.get():
                            font = self._get_sprite_font_by_name(self.countdown_sprite_font_var.get().strip())
                            if not font:
                                raise Exception("Sprite font not found")
                            if animation == "scroll_left":
                                line_img, sprite_err = self._build_sprite_text_line_image(
                                    countdown_text,
                                    font.get('path', ''),
                                    font.get('order', ''),
                                    font.get('cols', 1),
                                    self.countdown_bg_color
                                )
                                if line_img is None:
                                    raise Exception(sprite_err or "Sprite render failed")
                                self._start_sprite_scroll(line_img, self.countdown_bg_color, self.countdown_speed_var.get(), direction="left")
                                return
                            else:
                                def send_value(value_text):
                                    sprite_img, sprite_err = self._build_sprite_text_image(
                                        value_text,
                                        font.get('path', ''),
                                        font.get('order', ''),
                                        font.get('cols', 1),
                                        self.countdown_bg_color
                                    )
                                    if sprite_img is None:
                                        raise Exception(sprite_err or "Sprite render failed")
                                    tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_countdown_sprite.png')
                                    sprite_img.save(tmp_path, 'PNG')
                                    result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                    if asyncio.iscoroutine(result):
                                        self.run_async(result)

                                if animation == "static":
                                    delay_ms = max(1, int(self.countdown_static_delay_var.get() or 2)) * 1000
                                    frames = _build_countdown_frames()
                                    if len(frames) > 1:
                                        state = {'index': 0}

                                        def tick():
                                            send_value(frames[state['index']])
                                            state['index'] = (state['index'] + 1) % len(frames)
                                            self.countdown_static_timer = self.root.after(delay_ms, tick)

                                        tick()
                                    else:
                                        send_value(frames[0])
                                    return
                                send_value(countdown_text)
                        else:
                            if animation == "static":
                                delay_ms = max(1, int(self.countdown_static_delay_var.get() or 2)) * 1000
                                frames = _build_countdown_frames()
                                if len(frames) > 1:
                                    state = {'index': 0}

                                    def tick():
                                        color_hex = self.countdown_color.lstrip('#')
                                        bg_color_hex = self.countdown_bg_color.lstrip('#')
                                        inverted_speed = 101 - self.countdown_speed_var.get()
                                        result = self.client.send_text(
                                            text=frames[state['index']],
                                            char_height=16,
                                            color=color_hex,
                                            bg_color=bg_color_hex,
                                            animation=0,
                                            speed=inverted_speed
                                        )
                                        if asyncio.iscoroutine(result):
                                            self.run_async(result)
                                        state['index'] = (state['index'] + 1) % len(frames)
                                        self.countdown_static_timer = self.root.after(delay_ms, tick)

                                    tick()
                                else:
                                    color_hex = self.countdown_color.lstrip('#')
                                    bg_color_hex = self.countdown_bg_color.lstrip('#')
                                    inverted_speed = 101 - self.countdown_speed_var.get()
                                    result = self.client.send_text(
                                        text=frames[0],
                                        char_height=16,
                                        color=color_hex,
                                        bg_color=bg_color_hex,
                                        animation=0,
                                        speed=inverted_speed
                                    )
                                    if asyncio.iscoroutine(result):
                                        self.run_async(result)
                                return

                            color_hex = self.countdown_color.lstrip('#')
                            bg_color_hex = self.countdown_bg_color.lstrip('#')

                            # Invert speed: 1=slowest (100), 100=fastest (1)
                            inverted_speed = 101 - self.countdown_speed_var.get()

                            result = self.client.send_text(
                                text=countdown_text,
                                char_height=16,
                                color=color_hex,
                                bg_color=bg_color_hex,
                                animation=anim_map.get(animation, 0),
                                speed=inverted_speed
                            )

                            if asyncio.iscoroutine(result):
                                self.run_async(result)
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Countdown update failed: {error_msg}"))
                        self.root.after(0, self.stop_live_clock)
                
                threading.Thread(target=send_task, daemon=True).start()
                
                # Schedule next update
                if self.clock_running:
                    interval = self.countdown_update_interval_var.get() * 1000
                    self.clock_timer = self.root.after(interval, update_countdown)
            
            except Exception as e:
                messagebox.showerror("Error", f"Countdown error: {str(e)}")
                self.stop_live_clock()
        
        # Start the update loop
        update_countdown()
    
    def set_brightness(self):
        """Set display brightness"""
        self.set_brightness_btn.config(state=tk.DISABLED, text="Setting...")
        
        def send_task():
            try:
                result = self.client.set_brightness(self.brightness_var.get())
                if asyncio.iscoroutine(result):
                    self.run_async(result)
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to set brightness: {error_msg}"))
            finally:
                self.root.after(0, lambda: self.set_brightness_btn.config(state=tk.NORMAL, text="Set Brightness"))
        
        threading.Thread(target=send_task, daemon=True).start()
    
    def set_power(self, state):
        """Set display power state"""
        btn = self.power_on_btn if state else self.power_off_btn
        btn.config(state=tk.DISABLED)
        
        def send_task():
            try:
                result = self.client.set_power(state)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to set power: {error_msg}"))
            finally:
                self.root.after(0, lambda: btn.config(state=tk.NORMAL))
        
        threading.Thread(target=send_task, daemon=True).start()
    
    # ===== PRESET MANAGEMENT FUNCTIONS =====
    
    def load_presets(self):
        """Load presets from JSON file"""
        try:
            if os.path.exists(self.presets_file):
                with open(self.presets_file, 'r') as f:
                    self.presets = json.load(f)
        except Exception as e:
            print(f"Failed to load presets: {e}")
            self.presets = []
    
    def save_presets(self):
        """Save presets to JSON file"""
        try:
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save presets: {e}")
    
    def load_settings(self):
        """Load app settings from JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load settings: {e}")
        return {
            'auto_connect': True,
            'restore_last_state': True,
            'last_device': None,
            'last_preset': None,
            'weather_use_temp_images': False,
            'weather_temp_image_dir': ''
        }
    
    def save_settings(self):
        """Save app settings to JSON file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_secrets(self):
        """Load API keys from a secrets file"""
        try:
            if os.path.exists(self.secrets_file):
                with open(self.secrets_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            print(f"Failed to load secrets: {e}")
        return {
            'weather_api_key': '',
            'youtube_api_key': ''
        }

    def save_secrets(self):
        """Save API keys to a secrets file"""
        try:
            with open(self.secrets_file, 'w') as f:
                json.dump(self.secrets, f, indent=2)
        except Exception as e:
            print(f"Failed to save secrets: {e}")
    
    def auto_connect_to_last_device(self):
        """Automatically connect to the last connected device"""
        last_device = self.settings.get('last_device')
        if not last_device or self.is_connected:
            return
        
        # Set status
        self.status_label.config(text="Auto-connecting to last device...", foreground="blue")
        
        # Start scanning in background
        def scan_and_connect():
            try:
                # Wait for event loop to be ready
                import time
                for _ in range(10):
                    if self.loop and self.loop.is_running():
                        break
                    time.sleep(0.1)
                
                # Scan for devices
                future = asyncio.run_coroutine_threadsafe(self._scan_devices(), self.loop)
                devices = future.result(timeout=10)
                
                # Check if last device is available
                for device_name, device_addr in devices.items():
                    if device_addr == last_device:
                        # Found the device, connect
                        self.root.after(0, lambda: self._auto_connect_found(device_name, device_addr, devices))
                        return
                
                # Device not found
                self.root.after(0, lambda: self.status_label.config(
                    text="Last device not found. Please connect manually.", 
                    foreground="orange"))
            except Exception as e:
                print(f"Auto-connect failed: {e}")
                self.root.after(0, lambda: self.status_label.config(
                    text="Not connected", 
                    foreground="red"))
        
        threading.Thread(target=scan_and_connect, daemon=True).start()
    
    def _auto_connect_found(self, device_name, device_addr, devices):
        """Helper to connect after finding device"""
        self.devices_dict = devices
        self.device_combo['values'] = list(devices.keys())
        
        # Find and select the device in combo
        device_list = list(devices.keys())
        for i, name in enumerate(device_list):
            if devices[name] == device_addr:
                self.device_combo.current(i)
                break
        
        # Connect
        self.connect_device()
    
    def restore_last_state(self):
        """Restore the last displayed content"""
        if not self.is_connected:
            return
        
        last_preset_name = self.settings.get('last_preset')
        if not last_preset_name:
            return
        
        # Find the preset
        preset = next((p for p in self.presets if p['name'] == last_preset_name), None)
        if preset:
            self.execute_preset(preset)
    
    def generate_thumbnail(self, image_path, max_size=(64, 16)):
        """Generate a thumbnail from an image file and return as base64 string"""
        try:
            image_path = self._resolve_asset_path(image_path)
            if not os.path.exists(image_path):
                return None
            
            # Open and resize image
            img = Image.open(image_path)
            
            # Handle animated GIFs - get first frame
            if hasattr(img, 'is_animated') and img.is_animated:
                img.seek(0)
            
            # Convert RGBA to RGB if needed
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (0, 0, 0))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Crop to fill the thumbnail area (no black borders)
            img_ratio = img.width / img.height
            thumb_ratio = max_size[0] / max_size[1]
            
            if img_ratio > thumb_ratio:
                # Image is wider - crop width
                new_height = max_size[1]
                new_width = int(new_height * img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                left = (new_width - max_size[0]) // 2
                img = img.crop((left, 0, left + max_size[0], max_size[1]))
            else:
                # Image is taller - crop height
                new_width = max_size[0]
                new_height = int(new_width / img_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                top = (new_height - max_size[1]) // 2
                img = img.crop((0, top, max_size[0], top + max_size[1]))
            
            # Convert to base64
            import base64
            from io import BytesIO
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return img_str
        except Exception as e:
            print(f"Failed to generate thumbnail: {e}")
            return None
    
    def get_preset_preview(self, preset):
        """Generate preview text for a preset"""
        preset_type = preset.get('type', 'unknown')
        
        if preset_type == "text":
            text = preset.get('text', '')
            return text[:15] if len(text) <= 15 else text[:12] + "..."
        elif preset_type == "image":
            return "🖼️ Image"
        elif preset_type == "stock":
            ticker = preset.get('ticker', 'STOCK')
            return f"📈 {ticker}"
        elif preset_type == "youtube":
            channel = preset.get('channel', 'Channel')
            if channel.startswith('@'):
                return f"📺 {channel}"
            return "📺 YouTube"
        elif preset_type == "weather":
            location = preset.get('location', 'Location')
            return f"🌤️ {location}"
        elif preset_type == "animation":
            anim_type = preset.get('anim_type', 'animation')
            anim_names = {
                'game_of_life': '🎨 Life',
                'matrix': '🎨 Matrix',
                'fire': '🎨 Fire',
                'starfield': '🎨 Stars',
                'plasma': '🎨 Plasma'
            }
            return anim_names.get(anim_type, '🎨 Anim')
        elif preset_type == "clock":
            clock_mode = preset.get('clock_mode', 'builtin')
            if clock_mode == 'custom':
                format_preview = preset.get('time_format', '%H:%M:%S')
                import time
                return time.strftime(format_preview)
            elif clock_mode == 'countdown':
                event = preset.get('countdown_event', 'Event')
                return f"⏱️ {event}"
            else:
                return "🕐 Clock"
        return "..."
    
    def get_preset_details(self, preset):
        """Generate detail description for a preset"""
        preset_type = preset.get('type', 'unknown')
        
        if preset_type == "text":
            anim_names = {0: "Static", 1: "Scroll L", 2: "Scroll R", 4: "Flash"}
            anim = anim_names.get(preset.get('animation', 0), "Anim")
            rainbow = preset.get('rainbow', 0)
            if rainbow > 0:
                return f"{anim}, Rainbow {rainbow}"
            return anim
        elif preset_type == "image":
            path = preset.get('image_path', '')
            filename = os.path.basename(path) if path else "No file"
            return filename
        elif preset_type == "stock":
            ticker = preset.get('ticker', 'UNKNOWN')
            format_type = preset.get('format', 'price_change')
            format_names = {
                'price_change': 'Price + Change',
                'price_only': 'Price Only',
                'ticker_price': 'Ticker + Price'
            }
            auto_refresh = " (Auto)" if preset.get('auto_refresh', False) else ""
            return f"{ticker} - {format_names.get(format_type, format_type)}{auto_refresh}"
        elif preset_type == "youtube":
            channel = preset.get('channel', 'Unknown')
            auto_refresh = " (Auto)" if preset.get('auto_refresh', False) else ""
            return f"Logo + Subscribers{auto_refresh}"
        elif preset_type == "weather":
            location = preset.get('location', 'Unknown')
            unit = preset.get('unit', 'metric')
            unit_symbol = "°C" if unit == "metric" else "°F"
            auto_refresh = " (Auto)" if preset.get('auto_refresh', False) else ""
            return f"{location} ({unit_symbol}){auto_refresh}"
        elif preset_type == "animation":
            anim_type = preset.get('anim_type', 'game_of_life')
            anim_names = {
                'game_of_life': "Conway's Life",
                'matrix': 'Matrix Rain',
                'fire': 'Fire Effect',
                'starfield': 'Starfield',
                'plasma': 'Plasma'
            }
            color_scheme = preset.get('color_scheme', 'white')
            fps = preset.get('speed', 10)
            return f"{anim_names.get(anim_type, anim_type)} - {color_scheme.title()} @ {fps}fps"
        elif preset_type == "clock":
            clock_mode = preset.get('clock_mode', 'builtin')
            if clock_mode == 'custom':
                format_map = {
                    "%H:%M:%S": "24h with seconds",
                    "%H:%M": "24h",
                    "%I:%M:%S %p": "12h with seconds",
                    "%I:%M %p": "12h",
                }
                fmt = preset.get('time_format', '%H:%M:%S')
                return format_map.get(fmt, "Custom time")
            elif clock_mode == 'countdown':
                year = preset.get('countdown_year', 2026)
                month = preset.get('countdown_month', 1)
                day = preset.get('countdown_day', 1)
                return f"To {year}-{month:02d}-{day:02d}"
            else:
                style = preset.get('clock_style', 0)
                return f"Built-in style {style}"
        return ""
    
    def refresh_preset_buttons(self):
        """Refresh the preset buttons display"""
        # Clear existing buttons and cache
        for widget in self.presets_scrollable_frame.winfo_children():
            widget.destroy()
        self.thumbnail_cache.clear()
        
        if not self.presets:
            ttk.Label(self.presets_scrollable_frame, 
                     text="No presets saved yet. Use other tabs to create content, then save it as a preset.",
                     foreground="gray").pack(pady=20)
            return
        
        # Create buttons for each preset
        for idx, preset in enumerate(self.presets):
            preset_frame = ttk.Frame(self.presets_scrollable_frame, relief=tk.RIDGE, borderwidth=1)
            preset_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Get preview info
            preview_text = self.get_preset_preview(preset)
            preset_type = preset.get('type', 'unknown')
            
            # Preview label (left side) - colored background
            preview_frame = tk.Frame(preset_frame, width=128, height=32, bg='black')
            preview_frame.pack(side=tk.LEFT, padx=5, pady=5)
            preview_frame.pack_propagate(False)
            
            # Get colors for preview
            if preset_type == "text":
                fg_color = preset.get('text_color', '#FFFFFF')
                bg_color = preset.get('bg_color', '#000000')
            elif preset_type == "stock":
                fg_color = preset.get('text_color', '#00FF00')
                bg_color = preset.get('bg_color', '#000000')
            elif preset_type == "youtube":
                fg_color = preset.get('text_color', '#FFFFFF')
                bg_color = preset.get('bg_color', '#000000')
            elif preset_type == "weather":
                fg_color = preset.get('text_color', '#FFFFFF')
                bg_color = preset.get('bg_color', '#000000')
            elif preset_type == "animation":
                fg_color = '#FFFFFF'
                bg_color = '#000000'
            elif preset_type == "clock":
                clock_mode = preset.get('clock_mode', 'builtin')
                if clock_mode == 'custom':
                    fg_color = preset.get('clock_color', '#00ffff')
                    bg_color = preset.get('clock_bg_color', '#000000')
                elif clock_mode == 'countdown':
                    fg_color = preset.get('countdown_color', '#00ff00')
                    bg_color = preset.get('countdown_bg_color', '#000000')
                else:
                    fg_color = '#FFFFFF'
                    bg_color = '#000000'
            else:  # image
                fg_color = '#FFFFFF'
                bg_color = '#000000'
            
            preview_frame.config(bg=bg_color)
            
            # Check if preset has thumbnail data (for images/gifs)
            thumbnail_data = preset.get('thumbnail')
            if thumbnail_data and preset_type == "image":
                try:
                    # Decode base64 thumbnail and display
                    import base64
                    from io import BytesIO
                    img_data = base64.b64decode(thumbnail_data)
                    img = Image.open(BytesIO(img_data))
                    # Scale up 2x for better visibility
                    img = img.resize((128, 32), Image.Resampling.NEAREST)
                    photo = ImageTk.PhotoImage(img)
                    self.thumbnail_cache[f"thumb_{idx}"] = photo  # Keep reference
                    preview_label = tk.Label(preview_frame, image=photo, bg=bg_color)
                    preview_label.pack(expand=True)
                except Exception as e:
                    print(f"Failed to display thumbnail: {e}")
                    # Fallback to text
                    preview_label = tk.Label(preview_frame, text=preview_text, 
                                            fg=fg_color, bg=bg_color,
                                            font=('Courier', 8, 'bold'), wraplength=120)
                    preview_label.pack(expand=True)
            elif preset_type == "text":
                # Render actual text preview for text presets
                try:
                    text_content = preset.get('text', preview_text)
                    # Create image with text rendered at 64x16 (native resolution)
                    thumb_img = Image.new('RGB', (64, 16), bg_color)
                    draw = ImageDraw.Draw(thumb_img)
                    
                    # Try to load a font, fallback to default
                    try:
                        font = ImageFont.truetype("arial.ttf", 8)
                    except:
                        font = ImageFont.load_default()
                    
                    # Wrap text to fit 64 pixels width
                    words = text_content.split()
                    lines = []
                    current_line = []
                    for word in words:
                        test_line = ' '.join(current_line + [word])
                        bbox = draw.textbbox((0, 0), test_line, font=font)
                        if bbox[2] - bbox[0] <= 62:  # 2px margin
                            current_line.append(word)
                        else:
                            if current_line:
                                lines.append(' '.join(current_line))
                            current_line = [word]
                    if current_line:
                        lines.append(' '.join(current_line))
                    
                    # Limit to 2 lines (16px height)
                    lines = lines[:2]
                    
                    # Draw text centered
                    y_offset = (16 - len(lines) * 8) // 2
                    for i, line in enumerate(lines):
                        bbox = draw.textbbox((0, 0), line, font=font)
                        text_width = bbox[2] - bbox[0]
                        x = (64 - text_width) // 2
                        draw.text((x, y_offset + i * 8), line, fill=fg_color, font=font)
                    
                    # Scale up 2x for better visibility
                    thumb_img = thumb_img.resize((128, 32), Image.Resampling.NEAREST)
                    photo = ImageTk.PhotoImage(thumb_img)
                    self.thumbnail_cache[f"thumb_{idx}"] = photo
                    preview_label = tk.Label(preview_frame, image=photo, bg=bg_color)
                    preview_label.pack(expand=True)
                except Exception as e:
                    print(f"Failed to render text thumbnail: {e}")
                    # Fallback to simple label
                    preview_label = tk.Label(preview_frame, text=preview_text, 
                                            fg=fg_color, bg=bg_color,
                                            font=('Courier', 8, 'bold'), wraplength=120)
                    preview_label.pack(expand=True)
            else:
                # Clock or other presets - use text preview
                preview_label = tk.Label(preview_frame, text=preview_text, 
                                        fg=fg_color, bg=bg_color,
                                        font=('Courier', 8, 'bold'), wraplength=120)
                preview_label.pack(expand=True)
            
            # Info frame (middle)
            info_frame = ttk.Frame(preset_frame)
            info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            
            # Preset name and type
            name_label = ttk.Label(info_frame, text=preset.get('name', f'Preset {idx+1}'),
                                  font=('TkDefaultFont', 10, 'bold'))
            name_label.pack(anchor=tk.W)
            
            # Type and details
            type_icon = {"text": "📝", "image": "🖼️", "clock": "🕐", "stock": "📈", "youtube": "📺", "weather": "🌤️", "animation": "🎨"}.get(preset_type, "❓")
            details = self.get_preset_details(preset)
            details_label = ttk.Label(info_frame, text=f"{type_icon} {preset_type.upper()}: {details}",
                                     foreground="gray", font=('TkDefaultFont', 8))
            details_label.pack(anchor=tk.W)
            
            # Buttons frame (right side)
            btn_frame = ttk.Frame(preset_frame)
            btn_frame.pack(side=tk.RIGHT, padx=5, pady=5)
            
            # Execute button
            preset_btn = ttk.Button(btn_frame, text="▶️ Execute", width=12,
                                   command=lambda p=preset: self.execute_preset(p))
            preset_btn.pack(side=tk.TOP, pady=(0, 2))
            
            # Delete button
            del_btn = ttk.Button(btn_frame, text="🗑️ Delete", width=12,
                               command=lambda i=idx: self.delete_preset(i))
            del_btn.pack(side=tk.TOP)
    
    def save_current_preset(self):
        """Save current configuration as a preset"""
        # Ask for preset name
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Preset")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Preset Name:").pack(pady=(20, 5))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=(0, 10))
        name_entry.focus()
        
        # Type selection
        type_frame = ttk.Frame(dialog)
        type_frame.pack(pady=10)
        
        type_var = tk.StringVar(value="text")
        ttk.Label(type_frame, text="Type:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(type_frame, text="Text", variable=type_var, value="text").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Image", variable=type_var, value="image").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Clock", variable=type_var, value="clock").pack(side=tk.LEFT, padx=5)
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("No Name", "Please enter a preset name")
                return
            
            preset_type = type_var.get()
            preset = {"name": name, "type": preset_type}
            
            if preset_type == "text":
                preset["text"] = self.text_input.get("1.0", tk.END).strip()
                preset["text_color"] = self.text_color
                preset["bg_color"] = self.bg_color
                preset["char_height"] = 16
                preset["animation"] = self.animation_var.get()
                preset["speed"] = self.speed_var.get()
                preset["rainbow"] = self.rainbow_var.get()
                preset["text_use_sprite_font"] = self.text_use_sprite_var.get()
                preset["text_sprite_font_name"] = self.text_sprite_font_var.get().strip()
                preset["text_static_delay_seconds"] = int(self.text_static_delay_var.get() or 2)
            elif preset_type == "image":
                preset["image_path"] = self.image_path if hasattr(self, 'image_path') and self.image_path else ""
                # Generate thumbnail for image/gif
                if preset["image_path"] and os.path.exists(preset["image_path"]):
                    thumbnail = self.generate_thumbnail(preset["image_path"])
                    if thumbnail:
                        preset["thumbnail"] = thumbnail
            elif preset_type == "clock":
                # Save both built-in and custom clock settings
                preset["clock_mode"] = self.clock_mode_var.get()
                
                if preset["clock_mode"] == "builtin":
                    preset["clock_style"] = self.clock_style_var.get()
                elif preset["clock_mode"] == "custom":
                    preset["time_format"] = self.time_format_var.get()
                    preset["clock_color"] = self.clock_color
                    preset["clock_bg_color"] = self.clock_bg_color
                    preset["clock_animation"] = self.clock_animation_var.get()
                    preset["clock_update_interval"] = self.clock_update_interval_var.get()
                    preset["clock_use_time_sprite"] = self.clock_use_time_sprite_var.get()
                    preset["clock_time_sprite_font_name"] = self.clock_sprite_font_var.get().strip()
                else:  # countdown
                    preset["countdown_event"] = self.countdown_event_var.get()
                    preset["countdown_year"] = self.countdown_year_var.get()
                    preset["countdown_month"] = self.countdown_month_var.get()
                    preset["countdown_day"] = self.countdown_day_var.get()
                    preset["countdown_hour"] = self.countdown_hour_var.get()
                    preset["countdown_minute"] = self.countdown_minute_var.get()
                    preset["countdown_format"] = self.countdown_format_var.get()
                    preset["countdown_color"] = self.countdown_color
                    preset["countdown_bg_color"] = self.countdown_bg_color
                    preset["countdown_animation"] = self.countdown_animation_var.get()
                    preset["countdown_speed"] = self.countdown_speed_var.get()
                    preset["countdown_update_interval"] = self.countdown_update_interval_var.get()
                    preset["countdown_use_sprite_font"] = self.countdown_use_sprite_var.get()
                    preset["countdown_sprite_font_name"] = self.countdown_sprite_font_var.get().strip()
                    preset["countdown_static_delay_seconds"] = int(self.countdown_static_delay_var.get() or 2)
            
            self.presets.append(preset)
            self.save_presets()
            self.refresh_preset_buttons()
            dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save).pack(pady=10)
    
    def execute_preset(self, preset):
        """Execute a saved preset"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first")
            return
        
        # Stop any running live clock first
        if hasattr(self, 'clock_running') and self.clock_running:
            self.stop_live_clock()
        self._stop_sprite_scroll()
        if self.text_static_timer:
            self.root.after_cancel(self.text_static_timer)
            self.text_static_timer = None
        if self.countdown_static_timer:
            self.root.after_cancel(self.countdown_static_timer)
            self.countdown_static_timer = None
        
        # Stop any running stock auto-refresh
        self.stop_stock_refresh()
        
        # Save as last preset for state restoration
        self.settings['last_preset'] = preset.get('name')
        self.save_settings()
        
        preset_type = preset.get('type')
        
        try:
            if preset_type == "text":
                # Send text with saved settings
                def send_task():
                    try:
                        text = preset.get('text', '')
                        text_color_raw = preset.get('text_color', '#FFFFFF')
                        bg_color_raw = preset.get('bg_color', '#000000')

                        if preset.get('text_use_sprite_font', False):
                            font_name = preset.get('text_sprite_font_name', '').strip()
                            font = self._get_sprite_font_by_name(font_name)
                            if font:
                                anim = preset.get('animation', 0)
                                if anim in (1, 2):
                                    line_img, sprite_err = self._build_sprite_text_line_image(
                                        text,
                                        font.get('path', ''),
                                        font.get('order', ''),
                                        font.get('cols', 1),
                                        bg_color_raw
                                    )
                                    if line_img is None:
                                        raise Exception(sprite_err or "Sprite render failed")
                                    direction = "right" if anim == 2 else "left"
                                    self._start_sprite_scroll(line_img, bg_color_raw, preset.get('speed', 50), direction=direction)
                                    return
                                sprite_img, sprite_err = self._build_sprite_text_image(
                                    text,
                                    font.get('path', ''),
                                    font.get('order', ''),
                                    font.get('cols', 1),
                                    bg_color_raw
                                )
                            else:
                                legacy_path = preset.get('text_sprite_path', '').strip()
                                legacy_order = preset.get('text_sprite_order', '')
                                legacy_cols = preset.get('text_sprite_cols', 1)
                                if not legacy_path:
                                    raise Exception("Sprite font not found")
                                anim = preset.get('animation', 0)
                                if anim in (1, 2):
                                    line_img, sprite_err = self._build_sprite_text_line_image(
                                        text,
                                        legacy_path,
                                        legacy_order,
                                        legacy_cols,
                                        bg_color_raw
                                    )
                                    if line_img is None:
                                        raise Exception(sprite_err or "Sprite render failed")
                                    direction = "right" if anim == 2 else "left"
                                    self._start_sprite_scroll(line_img, bg_color_raw, preset.get('speed', 50), direction=direction)
                                    return
                                sprite_img, sprite_err = self._build_sprite_text_image(
                                    text,
                                    legacy_path,
                                    legacy_order,
                                    legacy_cols,
                                    bg_color_raw
                                )
                            if sprite_img is None:
                                raise Exception(sprite_err or "Sprite render failed")

                            if preset.get('animation', 0) == 0:
                                parts = [p.strip() for p in text.replace('|', '\n').splitlines() if p.strip()]
                                if len(parts) > 1:
                                    delay_ms = max(1, int(preset.get('text_static_delay_seconds', 2) or 2)) * 1000
                                    state = {'idx': 0}

                                    def tick():
                                        send_value = parts[state['idx']]
                                        sprite_img2, sprite_err2 = self._build_sprite_text_image(
                                            send_value,
                                            (font.get('path', '') if font else legacy_path),
                                            (font.get('order', '') if font else legacy_order),
                                            (font.get('cols', 1) if font else legacy_cols),
                                            bg_color_raw
                                        )
                                        if sprite_img2 is None:
                                            raise Exception(sprite_err2 or "Sprite render failed")
                                        tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_text_sprite.png')
                                        sprite_img2.save(tmp_path, 'PNG')
                                        result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                        if asyncio.iscoroutine(result):
                                            self.run_async(result)
                                        state['idx'] = (state['idx'] + 1) % len(parts)
                                        self.text_static_timer = self.root.after(delay_ms, tick)

                                    tick()
                                    return

                            tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_text_sprite.png')
                            sprite_img.save(tmp_path, 'PNG')
                            result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                            if asyncio.iscoroutine(result):
                                self.run_async(result)
                            return

                        text_color = text_color_raw.lstrip('#')
                        bg_color = bg_color_raw.lstrip('#')

                        if preset.get('animation', 0) == 0:
                            parts = [p.strip() for p in text.replace('|', '\n').splitlines() if p.strip()]
                            if len(parts) > 1:
                                delay_ms = max(1, int(preset.get('text_static_delay_seconds', 2) or 2)) * 1000
                                state = {'idx': 0}

                                def tick():
                                    value_text = parts[state['idx']]
                                    result = self.client.send_text(
                                        value_text,
                                        char_height=preset.get('char_height', 16),
                                        color=text_color,
                                        bg_color=bg_color,
                                        animation=0,
                                        speed=101 - preset.get('speed', 50),
                                        rainbow_mode=preset.get('rainbow', 0)
                                    )
                                    if asyncio.iscoroutine(result):
                                        self.run_async(result)
                                    state['idx'] = (state['idx'] + 1) % len(parts)
                                    self.text_static_timer = self.root.after(delay_ms, tick)

                                tick()
                                return

                        # Invert speed: 1=slowest (100), 100=fastest (1)
                        saved_speed = preset.get('speed', 50)
                        inverted_speed = 101 - saved_speed

                        result = self.client.send_text(
                            text,
                            char_height=preset.get('char_height', 16),
                            color=text_color,
                            bg_color=bg_color,
                            animation=preset.get('animation', 0),
                            speed=inverted_speed,
                            rainbow_mode=preset.get('rainbow', 0)
                        )

                        if asyncio.iscoroutine(result):
                            self.run_async(result)
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {error_msg}"))
                
                threading.Thread(target=send_task, daemon=True).start()
                
            elif preset_type == "image":
                image_path = self._resolve_asset_path(preset.get('image_path'))
                if image_path and os.path.exists(image_path):
                    def send_task():
                        try:
                            result = self.client.send_image(image_path, resize_method='crop', save_slot=0)
                            if asyncio.iscoroutine(result):
                                self.run_async(result)
                        except Exception as e:
                            error_msg = str(e)
                            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {error_msg}"))
                    
                    threading.Thread(target=send_task, daemon=True).start()
                else:
                    messagebox.showwarning("Image Not Found", "The image file for this preset no longer exists")
                    
            elif preset_type == "clock":
                clock_mode = preset.get('clock_mode', 'builtin')
                
                if clock_mode == "builtin":
                    # Built-in hardware clock
                    def send_task():
                        try:
                            result = self.client.set_clock_mode(style=preset.get('clock_style', 0))
                            if asyncio.iscoroutine(result):
                                self.run_async(result)
                        except Exception as e:
                            error_msg = str(e)
                            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {error_msg}"))
                    
                    threading.Thread(target=send_task, daemon=True).start()
                    
                elif clock_mode == "custom":
                    # Custom live clock - start it
                    import time
                    
                    time_format = preset.get('time_format', '%H:%M:%S')
                    clock_color = preset.get('clock_color', '#00ffff')
                    clock_bg_color = preset.get('clock_bg_color', '#000000')
                    clock_animation = preset.get('clock_animation', 'static')
                    update_interval = preset.get('clock_update_interval', 1)
                    clock_use_time_sprite = preset.get('clock_use_time_sprite', False)
                    clock_time_sprite_font_name = preset.get('clock_time_sprite_font_name', '').strip()

                    # Sync UI/state for sprite rendering colors
                    self.clock_color = clock_color
                    self.clock_bg_color = clock_bg_color
                    self.clock_color_canvas.config(bg=self.clock_color)
                    self.clock_bg_color_canvas.config(bg=self.clock_bg_color)
                    
                    # Stop any existing clock
                    if hasattr(self, 'clock_running') and self.clock_running:
                        self.stop_live_clock()
                    
                    self.clock_running = True
                    
                    def update_time():
                        if not self.clock_running:
                            return
                        
                        try:
                            current_time = time.strftime(time_format)
                            
                            anim_map = {
                                "static": 0,
                                "scroll_left": 1,
                                "flash": 4
                            }
                            
                            def send_task():
                                try:
                                    self.root.after(0, lambda t=current_time: self.clock_image_status_var.set(f"Clock tick: {t}"))

                                    if clock_use_time_sprite:
                                        self.clock_sprite_font_var.set(clock_time_sprite_font_name)
                                        sprite_img, sprite_err = self._build_time_sprite_image(current_time)
                                        if sprite_img is not None:
                                            tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_clock_sprite.png')
                                            sprite_img.save(tmp_path, 'PNG')
                                            self.root.after(0, lambda p=tmp_path: self.clock_image_status_var.set(f"Sprite image: {os.path.basename(p)}"))
                                            try:
                                                result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                                if asyncio.iscoroutine(result):
                                                    self.run_async(result)
                                                return
                                            except Exception as e:
                                                self.root.after(0, lambda: self.clock_image_status_var.set(f"Sprite send failed: {e}"))
                                        else:
                                            # Legacy fallback
                                            legacy_path = preset.get('clock_time_sprite_path', '').strip()
                                            legacy_order = preset.get('clock_time_sprite_order', '0123456789:')
                                            legacy_cols = preset.get('clock_time_sprite_cols', 11)
                                            if legacy_path:
                                                sprite_img, sprite_err = self._build_sprite_text_image(
                                                    current_time,
                                                    legacy_path,
                                                    legacy_order,
                                                    legacy_cols,
                                                    clock_bg_color
                                                )
                                                if sprite_img is not None:
                                                    tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_clock_sprite.png')
                                                    sprite_img.save(tmp_path, 'PNG')
                                                    self.root.after(0, lambda p=tmp_path: self.clock_image_status_var.set(f"Sprite image: {os.path.basename(p)}"))
                                                    try:
                                                        result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                                        if asyncio.iscoroutine(result):
                                                            self.run_async(result)
                                                        return
                                                    except Exception as e:
                                                        self.root.after(0, lambda: self.clock_image_status_var.set(f"Sprite send failed: {e}"))
                                            self.root.after(0, lambda: self.clock_image_status_var.set(f"Sprite error: {sprite_err} (fallback to text)"))
                                    else:
                                        self.root.after(0, lambda: self.clock_image_status_var.set("Sprite sheet disabled"))

                                    color_hex = clock_color.lstrip('#')
                                    bg_color_hex = clock_bg_color.lstrip('#')

                                    result = self.client.send_text(
                                        text=current_time,
                                        char_height=16,
                                        color=color_hex,
                                        bg_color=bg_color_hex,
                                        animation=anim_map.get(clock_animation, 0),
                                        speed=50
                                    )

                                    if asyncio.iscoroutine(result):
                                        self.run_async(result)
                                except Exception as e:
                                    error_msg = str(e)
                                    self.root.after(0, lambda: messagebox.showerror("Error", f"Clock update failed: {error_msg}"))
                                    self.clock_running = False
                            
                            threading.Thread(target=send_task, daemon=True).start()
                            
                            if self.clock_running:
                                interval = update_interval * 1000
                                self.clock_timer = self.root.after(interval, update_time)
                        
                        except Exception as e:
                            messagebox.showerror("Error", f"Clock error: {str(e)}")
                            self.clock_running = False
                    
                    update_time()
                    
                else:  # countdown
                    # Start countdown timer
                    from datetime import datetime
                    
                    event_name = preset.get('countdown_event', 'Event')
                    target_year = preset.get('countdown_year', 2026)
                    target_month = preset.get('countdown_month', 1)
                    target_day = preset.get('countdown_day', 1)
                    target_hour = preset.get('countdown_hour', 0)
                    target_minute = preset.get('countdown_minute', 0)
                    countdown_format = preset.get('countdown_format', 'days_hours_mins')
                    countdown_color = preset.get('countdown_color', '#00ff00')
                    countdown_bg_color = preset.get('countdown_bg_color', '#000000')
                    countdown_animation = preset.get('countdown_animation', 'static')
                    countdown_speed = preset.get('countdown_speed', 50)
                    update_interval = preset.get('countdown_update_interval', 60)
                    countdown_use_sprite_font = preset.get('countdown_use_sprite_font', False)
                    countdown_sprite_font_name = preset.get('countdown_sprite_font_name', '').strip()
                    countdown_static_delay_seconds = preset.get('countdown_static_delay_seconds', 2)
                    
                    # Stop any existing clock
                    if hasattr(self, 'clock_running') and self.clock_running:
                        self.stop_live_clock()
                    
                    self.clock_running = True
                    
                    try:
                        target_datetime = datetime(target_year, target_month, target_day, target_hour, target_minute)
                    except ValueError:
                        messagebox.showerror("Invalid Date", "The countdown preset has an invalid date")
                        return
                    
                    def update_countdown():
                        if not self.clock_running:
                            return
                        
                        try:
                            now = datetime.now()
                            format_choice = countdown_format
                            
                            if now >= target_datetime:
                                if format_choice == "with_name":
                                    countdown_text = f"{event_name}: NOW!"
                                else:
                                    countdown_text = "NOW!"
                            else:
                                delta = target_datetime - now
                                days = delta.days
                                hours, remainder = divmod(delta.seconds, 3600)
                                minutes, seconds = divmod(remainder, 60)
                                
                                if format_choice == "days_hours_mins":
                                    countdown_text = f"{days}d {hours}h {minutes}m"
                                elif format_choice == "days_hours":
                                    countdown_text = f"{days}d {hours}h"
                                elif format_choice == "hours_mins":
                                    total_hours = days * 24 + hours
                                    countdown_text = f"{total_hours}h {minutes}m"
                                elif format_choice == "days_only":
                                    countdown_text = f"{days} days"
                                elif format_choice == "with_name":
                                    countdown_text = f"{event_name}: {days}d {hours}h {minutes}m"
                                else:
                                    countdown_text = f"{days}d {hours}h {minutes}m"

                            def _build_countdown_frames():
                                if now >= target_datetime:
                                    if format_choice == "with_name":
                                        return [event_name.strip() or "Event", "NOW!"]
                                    return ["NOW!"]

                                if format_choice == "with_name":
                                    return [
                                        event_name.strip() or "Event",
                                        f"{days}d",
                                        f"{hours}h {minutes}m"
                                    ]
                                if format_choice == "days_hours_mins":
                                    return [f"{days}d", f"{hours}h {minutes}m"]
                                if format_choice == "days_hours":
                                    return [f"{days}d", f"{hours}h"]
                                if format_choice == "hours_mins":
                                    total_hours = days * 24 + hours
                                    return [f"{total_hours}h", f"{minutes}m"]
                                if format_choice == "days_only":
                                    return [f"{days} days"]
                                return [f"{days}d", f"{hours}h {minutes}m"]
                            
                            anim_map = {
                                "static": 0,
                                "scroll_left": 1,
                                "flash": 4
                            }
                            
                            def send_task():
                                try:
                                    if countdown_use_sprite_font:
                                        font = self._get_sprite_font_by_name(countdown_sprite_font_name)
                                        if font:
                                            if countdown_animation == "scroll_left":
                                                line_img, sprite_err = self._build_sprite_text_line_image(
                                                    countdown_text,
                                                    font.get('path', ''),
                                                    font.get('order', ''),
                                                    font.get('cols', 1),
                                                    countdown_bg_color
                                                )
                                                if line_img is None:
                                                    raise Exception(sprite_err or "Sprite render failed")
                                                self._start_sprite_scroll(line_img, countdown_bg_color, countdown_speed, direction="left")
                                                return
                                            if countdown_animation == "static":
                                                delay_ms = max(1, int(countdown_static_delay_seconds or 2)) * 1000
                                                frames = _build_countdown_frames()
                                                if len(frames) > 1:
                                                    state = {'index': 0}

                                                    def tick():
                                                        value_text = frames[state['index']]
                                                        sprite_img2, sprite_err2 = self._build_sprite_text_image(
                                                            value_text,
                                                            font.get('path', ''),
                                                            font.get('order', ''),
                                                            font.get('cols', 1),
                                                            countdown_bg_color
                                                        )
                                                        if sprite_img2 is None:
                                                            raise Exception(sprite_err2 or "Sprite render failed")
                                                        tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_countdown_sprite.png')
                                                        sprite_img2.save(tmp_path, 'PNG')
                                                        result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                                        if asyncio.iscoroutine(result):
                                                            self.run_async(result)
                                                        state['index'] = (state['index'] + 1) % len(frames)
                                                        self.countdown_static_timer = self.root.after(delay_ms, tick)

                                                    tick()
                                                else:
                                                    value_text = frames[0]
                                                    sprite_img2, sprite_err2 = self._build_sprite_text_image(
                                                        value_text,
                                                        font.get('path', ''),
                                                        font.get('order', ''),
                                                        font.get('cols', 1),
                                                        countdown_bg_color
                                                    )
                                                    if sprite_img2 is None:
                                                        raise Exception(sprite_err2 or "Sprite render failed")
                                                    tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_countdown_sprite.png')
                                                    sprite_img2.save(tmp_path, 'PNG')
                                                    result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                                    if asyncio.iscoroutine(result):
                                                        self.run_async(result)
                                                return
                                            sprite_img, sprite_err = self._build_sprite_text_image(
                                                countdown_text,
                                                font.get('path', ''),
                                                font.get('order', ''),
                                                font.get('cols', 1),
                                                countdown_bg_color
                                            )
                                        else:
                                            legacy_path = preset.get('countdown_sprite_path', '').strip()
                                            legacy_order = preset.get('countdown_sprite_order', '')
                                            legacy_cols = preset.get('countdown_sprite_cols', 1)
                                            if not legacy_path:
                                                raise Exception("Sprite font not found")
                                            if countdown_animation == "scroll_left":
                                                line_img, sprite_err = self._build_sprite_text_line_image(
                                                    countdown_text,
                                                    legacy_path,
                                                    legacy_order,
                                                    legacy_cols,
                                                    countdown_bg_color
                                                )
                                                if line_img is None:
                                                    raise Exception(sprite_err or "Sprite render failed")
                                                self._start_sprite_scroll(line_img, countdown_bg_color, countdown_speed, direction="left")
                                                return
                                            if countdown_animation == "static":
                                                delay_ms = max(1, int(countdown_static_delay_seconds or 2)) * 1000
                                                frames = _build_countdown_frames()
                                                if len(frames) > 1:
                                                    state = {'index': 0}

                                                    def tick():
                                                        value_text = frames[state['index']]
                                                        sprite_img2, sprite_err2 = self._build_sprite_text_image(
                                                            value_text,
                                                            legacy_path,
                                                            legacy_order,
                                                            legacy_cols,
                                                            countdown_bg_color
                                                        )
                                                        if sprite_img2 is None:
                                                            raise Exception(sprite_err2 or "Sprite render failed")
                                                        tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_countdown_sprite.png')
                                                        sprite_img2.save(tmp_path, 'PNG')
                                                        result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                                        if asyncio.iscoroutine(result):
                                                            self.run_async(result)
                                                        state['index'] = (state['index'] + 1) % len(frames)
                                                        self.countdown_static_timer = self.root.after(delay_ms, tick)

                                                    tick()
                                                else:
                                                    value_text = frames[0]
                                                    sprite_img2, sprite_err2 = self._build_sprite_text_image(
                                                        value_text,
                                                        legacy_path,
                                                        legacy_order,
                                                        legacy_cols,
                                                        countdown_bg_color
                                                    )
                                                    if sprite_img2 is None:
                                                        raise Exception(sprite_err2 or "Sprite render failed")
                                                    tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_countdown_sprite.png')
                                                    sprite_img2.save(tmp_path, 'PNG')
                                                    result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                                    if asyncio.iscoroutine(result):
                                                        self.run_async(result)
                                                return
                                            sprite_img, sprite_err = self._build_sprite_text_image(
                                                countdown_text,
                                                legacy_path,
                                                legacy_order,
                                                legacy_cols,
                                                countdown_bg_color
                                            )
                                        if sprite_img is None:
                                            raise Exception(sprite_err or "Sprite render failed")
                                        tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_countdown_sprite.png')
                                        sprite_img.save(tmp_path, 'PNG')
                                        result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                        if asyncio.iscoroutine(result):
                                            self.run_async(result)
                                    else:
                                        if countdown_animation == "static":
                                            delay_ms = max(1, int(countdown_static_delay_seconds or 2)) * 1000
                                            frames = _build_countdown_frames()
                                            if len(frames) > 1:
                                                state = {'index': 0}

                                                def tick():
                                                    value_text = frames[state['index']]
                                                    color_hex = countdown_color.lstrip('#')
                                                    bg_color_hex = countdown_bg_color.lstrip('#')
                                                    inverted_speed = 101 - countdown_speed
                                                    result = self.client.send_text(
                                                        text=value_text,
                                                        char_height=16,
                                                        color=color_hex,
                                                        bg_color=bg_color_hex,
                                                        animation=0,
                                                        speed=inverted_speed
                                                    )
                                                    if asyncio.iscoroutine(result):
                                                        self.run_async(result)
                                                    state['index'] = (state['index'] + 1) % len(frames)
                                                    self.countdown_static_timer = self.root.after(delay_ms, tick)

                                                tick()
                                            else:
                                                color_hex = countdown_color.lstrip('#')
                                                bg_color_hex = countdown_bg_color.lstrip('#')
                                                inverted_speed = 101 - countdown_speed
                                                result = self.client.send_text(
                                                    text=frames[0],
                                                    char_height=16,
                                                    color=color_hex,
                                                    bg_color=bg_color_hex,
                                                    animation=0,
                                                    speed=inverted_speed
                                                )
                                                if asyncio.iscoroutine(result):
                                                    self.run_async(result)
                                            return

                                        color_hex = countdown_color.lstrip('#')
                                        bg_color_hex = countdown_bg_color.lstrip('#')

                                        # Invert speed: 1=slowest (100), 100=fastest (1)
                                        inverted_speed = 101 - countdown_speed

                                        result = self.client.send_text(
                                            text=countdown_text,
                                            char_height=16,
                                            color=color_hex,
                                            bg_color=bg_color_hex,
                                            animation=anim_map.get(countdown_animation, 0),
                                            speed=inverted_speed
                                        )

                                        if asyncio.iscoroutine(result):
                                            self.run_async(result)
                                except Exception as e:
                                    error_msg = str(e)
                                    self.root.after(0, lambda: messagebox.showerror("Error", f"Countdown update failed: {error_msg}"))
                                    self.clock_running = False
                            
                            threading.Thread(target=send_task, daemon=True).start()
                            
                            if self.clock_running:
                                interval = update_interval * 1000
                                self.clock_timer = self.root.after(interval, update_countdown)
                        
                        except Exception as e:
                            messagebox.showerror("Error", f"Countdown error: {str(e)}")
                            self.clock_running = False
                    
                    update_countdown()
                
            elif preset_type == "stock":
                # Execute stock preset - fetch and display
                ticker = preset.get('ticker', 'AAPL')
                format_type = preset.get('format', 'price_change')
                bg_color = preset.get('bg_color', '#000000')
                animation = preset.get('animation', 0)  # 0=scroll left (default)
                speed = preset.get('speed', 30)
                auto_refresh = preset.get('auto_refresh', False)
                refresh_interval = preset.get('refresh_interval', 60)
                stock_sprite_font_name = preset.get('stock_sprite_font_name', '').strip()
                stock_static_delay_seconds = preset.get('stock_static_delay_seconds', 2)
                
                def fetch_and_send():
                    try:
                        import yfinance as yf
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        
                        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                        previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
                        
                        if current_price is None:
                            self.root.after(0, lambda: messagebox.showerror(
                                "Stock Error", f"Could not fetch data for {ticker}"))
                            return
                        
                        change = current_price - previous_close if previous_close else 0
                        change_percent = (change / previous_close * 100) if previous_close else 0
                        
                        # Format price to max 7 characters
                        price_str = self.format_stock_price(current_price)
                        
                        # Format text
                        if format_type == "price_change":
                            change_symbol = "↑" if change >= 0 else "↓"
                            text = f"{price_str} {change_symbol}{abs(change_percent):.1f}%"
                        elif format_type == "price_only":
                            text = price_str
                        else:  # ticker_price
                            text = f"{ticker} {price_str}"

                        def send_text_value(value_text):
                            def send_task():
                                try:
                                    font = self._get_sprite_font_by_name(stock_sprite_font_name)
                                    if not font:
                                        legacy_path = preset.get('stock_sprite_path', '').strip()
                                        legacy_order = preset.get('stock_sprite_order', '')
                                        legacy_cols = preset.get('stock_sprite_cols', 1)
                                        if not legacy_path:
                                            raise Exception("Sprite font not found")
                                        if animation in (1, 2):
                                            line_img, sprite_err = self._build_sprite_text_line_image(
                                                value_text,
                                                legacy_path,
                                                legacy_order,
                                                legacy_cols,
                                                bg_color
                                            )
                                            if line_img is None:
                                                raise Exception(sprite_err or "Sprite render failed")
                                            direction = "right" if animation == 2 else "left"
                                            self._start_sprite_scroll(line_img, bg_color, speed, direction=direction)
                                            return
                                        sprite_img, sprite_err = self._build_sprite_text_image(
                                            value_text,
                                            legacy_path,
                                            legacy_order,
                                            legacy_cols,
                                            bg_color
                                        )
                                    else:
                                        if animation in (1, 2):
                                            line_img, sprite_err = self._build_sprite_text_line_image(
                                                value_text,
                                                font.get('path', ''),
                                                font.get('order', ''),
                                                font.get('cols', 1),
                                                bg_color
                                            )
                                            if line_img is None:
                                                raise Exception(sprite_err or "Sprite render failed")
                                            direction = "right" if animation == 2 else "left"
                                            self._start_sprite_scroll(line_img, bg_color, speed, direction=direction)
                                            return
                                        sprite_img, sprite_err = self._build_sprite_text_image(
                                            value_text,
                                            font.get('path', ''),
                                            font.get('order', ''),
                                            font.get('cols', 1),
                                            bg_color
                                        )

                                    if sprite_img is None:
                                        raise Exception(sprite_err or "Sprite render failed")
                                    tmp_path = os.path.join(tempfile.gettempdir(), 'ipixel_stock_sprite.png')
                                    sprite_img.save(tmp_path, 'PNG')
                                    result = self.client.send_image(tmp_path, resize_method='crop', save_slot=0)
                                    if asyncio.iscoroutine(result):
                                        self.run_async(result)
                                except Exception as e:
                                    error_msg = str(e)
                                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to send: {error_msg}"))

                            threading.Thread(target=send_task, daemon=True).start()

                        def start_static_cycle():
                            if self.stock_static_timer:
                                self.root.after_cancel(self.stock_static_timer)
                            state = {'show_ticker': True}
                            delay_ms = max(1, int(stock_static_delay_seconds or 2)) * 1000

                            def tick():
                                if format_type == "ticker_price":
                                    send_text_value(ticker if state['show_ticker'] else price_str)
                                    state['show_ticker'] = not state['show_ticker']
                                elif format_type == "price_change":
                                    change_symbol = "↑" if change >= 0 else "↓"
                                    change_text = f"{change_symbol}{abs(change_percent):.1f}%"
                                    send_text_value(price_str if state['show_ticker'] else change_text)
                                    state['show_ticker'] = not state['show_ticker']
                                else:
                                    send_text_value(price_str)
                                self.stock_static_timer = self.root.after(delay_ms, tick)

                            tick()

                        if animation == 0 and format_type in ("ticker_price", "price_change"):
                            start_static_cycle()
                        else:
                            send_text_value(text)
                        
                        # Schedule auto-refresh
                        if auto_refresh:
                            # Cancel previous stock refresh timer if running
                            if self.stock_refresh_timer:
                                self.root.after_cancel(self.stock_refresh_timer)
                            interval_ms = refresh_interval * 1000
                            self.stock_refresh_timer = self.root.after(interval_ms, fetch_and_send)
                        
                    except ImportError:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Missing Library", 
                            "yfinance library not installed.\n\nInstall with: pip install yfinance"))
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda: messagebox.showerror("Stock Error", f"Error: {error_msg}"))
                
                threading.Thread(target=fetch_and_send, daemon=True).start()
            
            elif preset_type == "youtube":
                # Execute YouTube preset
                self.youtube_channel_var.set(preset.get('channel', ''))
                self.youtube_text_color = preset.get('text_color', '#FFFFFF')
                self.youtube_bg_color = preset.get('bg_color', '#000000')
                self.youtube_auto_refresh_var.set(preset.get('auto_refresh', False))
                self.youtube_refresh_interval_var.set(preset.get('refresh_interval', 300))
                self.youtube_use_sprite_var.set(preset.get('youtube_use_sprite_font', False))
                self.youtube_sprite_font_var.set(preset.get('youtube_sprite_font_name', '').strip())
                self.youtube_show_logo_var.set(preset.get('youtube_show_logo', False))
                self.youtube_logo_path_var.set(preset.get('youtube_logo_path', os.path.join("Gallery", "Sprites", "YT-btn.png")))
                self.update_youtube_sprite_settings()
                self.update_youtube_logo_settings()
                
                # Fetch and send
                self.fetch_youtube_stats()
                self.root.after(2000, self.send_youtube_to_display)  # Wait for fetch to complete
            
            elif preset_type == "weather":
                # Execute Weather preset
                self.weather_location_var.set(preset.get('location', ''))
                self.weather_unit_var.set(preset.get('unit', 'metric'))
                self.weather_format_var.set(preset.get('format', 'temp_condition'))
                self.weather_text_color = preset.get('text_color', '#FFFFFF')
                self.weather_bg_color = preset.get('bg_color', '#000000')
                self.weather_animation_var.set(preset.get('animation', 'scroll'))
                self.weather_speed_var.set(preset.get('speed', 50))
                self.weather_auto_refresh_var.set(preset.get('auto_refresh', False))
                self.weather_refresh_interval_var.set(preset.get('refresh_interval', 600))
                
                # Fetch and send
                self.fetch_weather_data()
                self.root.after(2000, self.send_weather_to_display)  # Wait for fetch to complete
            
            elif preset_type == "animation":
                # Execute Animation preset
                self.anim_type_var.set(preset.get('anim_type', 'game_of_life'))
                self.anim_color_scheme_var.set(preset.get('color_scheme', 'white'))
                self.anim_speed_var.set(preset.get('speed', 10))
                self.anim_duration_var.set(preset.get('duration', 30))
                self.gol_density_var.set(preset.get('gol_density', 30))
                
                # Start animation
                self.send_animation_to_display()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute preset: {str(e)}")
    
    def delete_preset(self, index):
        """Delete a preset"""
        if messagebox.askyesno("Delete Preset", f"Delete preset '{self.presets[index]['name']}'?"):
            del self.presets[index]
            self.save_presets()
            self.refresh_preset_buttons()
    
    def import_presets(self):
        """Import presets from a JSON file"""
        filepath = filedialog.askopenfilename(
            title="Import Presets",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    imported = json.load(f)
                    if isinstance(imported, list):
                        self.presets.extend(imported)
                        self.save_presets()
                        self.refresh_preset_buttons()
                    else:
                        messagebox.showerror("Error", "Invalid preset file format")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import: {str(e)}")
    
    def export_presets(self):
        """Export presets to a JSON file"""
        if not self.presets:
            messagebox.showwarning("No Presets", "No presets to export")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Export Presets",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(self.presets, f, indent=2)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def edit_playlist(self):
        """Open dialog to edit playlist"""
        if not self.presets:
            return
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Playlist")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Instructions
        ttk.Label(dialog, text="Build your playlist by adding presets with display duration",
                 font=('TkDefaultFont', 9, 'italic')).pack(pady=(10, 5))
        
        # Current playlist
        list_frame = ttk.LabelFrame(dialog, text="Playlist Items", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # Listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        playlist_listbox = tk.Listbox(list_container, height=15)
        list_scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=playlist_listbox.yview)
        playlist_listbox.configure(yscrollcommand=list_scrollbar.set)
        
        playlist_listbox.pack(side="left", fill="both", expand=True)
        list_scrollbar.pack(side="right", fill="y")
        
        def refresh_playlist_display():
            playlist_listbox.delete(0, tk.END)
            for i, item in enumerate(self.playlist):
                preset_name = item['preset_name']
                duration = item.get('duration', 0)
                use_anim_duration = item.get('use_anim_duration', False)
                if use_anim_duration:
                    duration_text = "anim"
                else:
                    duration_text = f"{duration:.1f}" if isinstance(duration, float) and not duration.is_integer() else f"{int(duration)}"
                playlist_listbox.insert(tk.END, f"{i+1}. {preset_name} ({duration_text}s)")
        
        refresh_playlist_display()
        
        # Add preset controls
        add_frame = ttk.LabelFrame(dialog, text="Add Preset to Playlist", padding="10")
        add_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        add_controls = ttk.Frame(add_frame)
        add_controls.pack(fill=tk.X)
        
        ttk.Label(add_controls, text="Preset:").pack(side=tk.LEFT, padx=(0, 5))
        
        preset_var = tk.StringVar()
        preset_names = [p['name'] for p in self.presets]
        preset_combo = ttk.Combobox(add_controls, textvariable=preset_var, 
                                    values=preset_names, state='readonly', width=30)
        if preset_names:
            preset_combo.current(0)
        preset_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(add_controls, text="Duration (seconds):").pack(side=tk.LEFT, padx=(0, 5))
        
        duration_var = tk.DoubleVar(value=10.0)
        duration_spin = ttk.Spinbox(add_controls, from_=0.1, to=3600, increment=0.1, textvariable=duration_var, width=10)
        duration_spin.pack(side=tk.LEFT, padx=(0, 10))

        use_anim_duration_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(add_controls, text="Use animation duration", variable=use_anim_duration_var).pack(side=tk.LEFT, padx=(10, 0))
        
        def add_to_playlist():
            if not preset_var.get():
                return
            try:
                duration_value = float(duration_var.get())
            except Exception:
                duration_value = 10.0
            if duration_value <= 0:
                duration_value = 0.1
            self.playlist.append({
                'preset_name': preset_var.get(),
                'duration': duration_value,
                'use_anim_duration': use_anim_duration_var.get()
            })
            refresh_playlist_display()
        
        ttk.Button(add_controls, text="➕ Add", command=add_to_playlist).pack(side=tk.LEFT)
        
        # Playlist controls
        control_frame = ttk.Frame(dialog)
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        def move_up():
            selection = playlist_listbox.curselection()
            if selection and selection[0] > 0:
                idx = selection[0]
                self.playlist[idx], self.playlist[idx-1] = self.playlist[idx-1], self.playlist[idx]
                refresh_playlist_display()
                playlist_listbox.selection_set(idx-1)
        
        def move_down():
            selection = playlist_listbox.curselection()
            if selection and selection[0] < len(self.playlist) - 1:
                idx = selection[0]
                self.playlist[idx], self.playlist[idx+1] = self.playlist[idx+1], self.playlist[idx]
                refresh_playlist_display()
                playlist_listbox.selection_set(idx+1)
        
        def remove_item():
            selection = playlist_listbox.curselection()
            if selection:
                self.playlist.pop(selection[0])
                refresh_playlist_display()
        
        def clear_playlist():
            if messagebox.askyesno("Clear Playlist", "Remove all items from playlist?"):
                self.playlist.clear()
                refresh_playlist_display()
        
        ttk.Button(control_frame, text="⬆️ Move Up", command=move_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="⬇️ Move Down", command=move_down).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="🗑️ Remove", command=remove_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="Clear All", command=clear_playlist).pack(side=tk.LEFT, padx=(10, 0))
        
        # Done button
        ttk.Button(dialog, text="Done", command=dialog.destroy, width=15).pack(pady=(0, 10))
    
    def play_playlist(self):
        """Start playing the playlist"""
        if not self.playlist:
            return
        
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Connect to device first")
            return
        
        if self.playlist_running and self.playlist_paused:
            # Resume
            self.playlist_paused = False
            self.playlist_status_var.set(f"Playlist: Playing ({self.playlist_index + 1}/{len(self.playlist)})")
            self.schedule_next_preset()
        else:
            # Start from beginning
            self.playlist_running = True
            self.playlist_paused = False
            self.playlist_index = 0
            self.playlist_status_var.set(f"Playlist: Playing ({self.playlist_index + 1}/{len(self.playlist)})")
            self.play_next_preset()
    
    def pause_playlist(self):
        """Pause the playlist"""
        if self.playlist_running and not self.playlist_paused:
            self.playlist_paused = True
            if self.playlist_timer:
                self.root.after_cancel(self.playlist_timer)
                self.playlist_timer = None
            self.playlist_status_var.set(f"Playlist: Paused ({self.playlist_index + 1}/{len(self.playlist)})")
    
    def stop_playlist(self):
        """Stop the playlist"""
        self.playlist_running = False
        self.playlist_paused = False
        self.playlist_index = 0
        if self.playlist_timer:
            self.root.after_cancel(self.playlist_timer)
            self.playlist_timer = None
        self.playlist_status_var.set("Playlist: Not running")
    
    def play_next_preset(self):
        """Play the current preset in the playlist"""
        if not self.playlist_running or self.playlist_paused:
            return
        
        if self.playlist_index >= len(self.playlist):
            # Loop back to start
            self.playlist_index = 0
        
        item = self.playlist[self.playlist_index]
        preset_name = item['preset_name']
        duration = float(item.get('duration', 0))
        use_anim_duration = item.get('use_anim_duration', False)
        
        # Find and execute the preset
        preset = next((p for p in self.presets if p['name'] == preset_name), None)
        if preset:
            self.playlist_status_var.set(f"Playlist: Playing '{preset_name}' ({self.playlist_index + 1}/{len(self.playlist)})")
            threading.Thread(target=self.execute_preset, args=(preset,), daemon=True).start()

            # Schedule next preset
            delay_seconds = duration
            if use_anim_duration and preset.get('type') == 'animation':
                anim_duration = float(preset.get('duration', 0) or 0)
                if anim_duration <= 0:
                    anim_duration = float(self.anim_duration_var.get() or 0)
                if anim_duration > 0:
                    delay_seconds = anim_duration
                    self.playlist_status_var.set(
                        f"Playlist: Playing '{preset_name}' (anim {anim_duration}s)"
                    )
                else:
                    self.playlist_status_var.set(
                        f"Playlist: Playing '{preset_name}' (anim=0, using {duration}s)"
                    )
            if delay_seconds <= 0:
                delay_seconds = 0.1
            self.schedule_next_preset(delay_seconds)
        else:
            # Preset not found, skip to next
            self.playlist_index += 1
            self.play_next_preset()
    
    def schedule_next_preset(self, delay_seconds=None):
        """Schedule the next preset to play"""
        if delay_seconds is None and self.playlist_index < len(self.playlist):
            delay_seconds = self.playlist[self.playlist_index]['duration']
        
        if delay_seconds and self.playlist_running and not self.playlist_paused:
            self.playlist_index += 1
            delay_ms = max(1, int(round(delay_seconds * 1000)))
            self.playlist_timer = self.root.after(delay_ms, self.play_next_preset)
    
    def save_playlist(self):
        """Save current playlist to a file"""
        if not self.playlist:
            messagebox.showwarning("Empty Playlist", "Create a playlist first before saving")
            return
        
        # Ask for playlist name
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Playlist")
        dialog.geometry("400x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Playlist Name:").pack(pady=(20, 5))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=(0, 10))
        name_entry.focus()
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("No Name", "Please enter a playlist name")
                return
            
            # Create playlists directory if it doesn't exist
            playlists_dir = "playlists"
            if not os.path.exists(playlists_dir):
                os.makedirs(playlists_dir)
            
            filename = os.path.join(playlists_dir, f"{name}.json")
            
            try:
                playlist_data = {
                    "name": name,
                    "items": self.playlist
                }
                
                with open(filename, 'w') as f:
                    json.dump(playlist_data, f, indent=2)
                
                self.current_playlist_file = filename
                self.current_playlist_name_var.set(f"📋 {name}")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save playlist: {str(e)}")
        
        ttk.Button(dialog, text="Save", command=save).pack(pady=10)
    
    def load_playlist_dialog(self):
        """Show dialog to select and load a playlist"""
        playlists_dir = "playlists"
        
        # Check if playlists directory exists
        if not os.path.exists(playlists_dir):
            messagebox.showinfo("No Playlists", "No saved playlists found. Create and save a playlist first.")
            return
        
        # Get all playlist files
        playlist_files = [f for f in os.listdir(playlists_dir) if f.endswith('.json')]
        
        if not playlist_files:
            messagebox.showinfo("No Playlists", "No saved playlists found. Create and save a playlist first.")
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Playlist")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Select a playlist to load:", 
                 font=('TkDefaultFont', 10, 'bold')).pack(pady=(10, 5))
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        playlist_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=10)
        playlist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=playlist_listbox.yview)
        
        # Populate listbox
        for filename in sorted(playlist_files):
            display_name = filename[:-5]  # Remove .json extension
            playlist_listbox.insert(tk.END, display_name)
        
        def load_selected():
            selection = playlist_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a playlist")
                return
            
            filename = playlist_files[selection[0]]
            filepath = os.path.join(playlists_dir, filename)
            
            try:
                with open(filepath, 'r') as f:
                    playlist_data = json.load(f)
                
                self.playlist = playlist_data.get('items', [])
                self.current_playlist_file = filepath
                self.current_playlist_name_var.set(f"📋 {playlist_data.get('name', filename[:-5])}")
                dialog.destroy()
                messagebox.showinfo("Success", f"Loaded playlist with {len(self.playlist)} item(s)")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load playlist: {str(e)}")
        
        def delete_selected():
            selection = playlist_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a playlist to delete")
                return
            
            filename = playlist_files[selection[0]]
            display_name = filename[:-5]
            
            if messagebox.askyesno("Confirm Delete", f"Delete playlist '{display_name}'?"):
                try:
                    os.remove(os.path.join(playlists_dir, filename))
                    playlist_listbox.delete(selection[0])
                    playlist_files.pop(selection[0])
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete: {str(e)}")
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 10))
        
        ttk.Button(btn_frame, text="Load", command=load_selected, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete", command=delete_selected, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)


def main():
    root = tk.Tk()
    app = iPixelController(root)
    root.mainloop()


if __name__ == "__main__":
    main()
