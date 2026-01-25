"""
Settings panel for device and application configuration.

Handles brightness, power control, and sprite font management.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, Optional, Callable, List


class SettingsPanel(ttk.Frame):
    """
    Settings panel widget.

    Provides UI for:
    - Device brightness control
    - Power on/off
    - Sprite font library management
    """

    def __init__(
        self,
        parent,
        config,
        device_manager,
        state,
        on_sprite_fonts_changed: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, padding="10", **kwargs)

        self.config = config
        self.device_manager = device_manager
        self.state = state
        self.on_sprite_fonts_changed = on_sprite_fonts_changed

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the settings UI."""
        self.columnconfigure(1, weight=1)

        # Brightness control
        ttk.Label(self, text="Brightness:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        self.brightness_var = tk.IntVar(value=50)
        brightness_frame = ttk.Frame(self)
        brightness_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Scale(
            brightness_frame,
            from_=1,
            to=100,
            variable=self.brightness_var,
            orient=tk.HORIZONTAL,
            length=300
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(brightness_frame, textvariable=self.brightness_var).pack(side=tk.LEFT)

        self.set_brightness_btn = ttk.Button(
            self,
            text="Set Brightness",
            command=self._set_brightness,
            state=tk.DISABLED
        )
        self.set_brightness_btn.grid(row=1, column=0, columnspan=2, pady=(0, 20))

        # Power control
        ttk.Label(self, text="Power Control:").grid(row=2, column=0, sticky=tk.W, pady=(0, 10))

        power_frame = ttk.Frame(self)
        power_frame.grid(row=2, column=1, sticky=tk.W, pady=(0, 10))

        self.power_on_btn = ttk.Button(
            power_frame,
            text="Power ON",
            command=lambda: self._set_power(True),
            state=tk.DISABLED
        )
        self.power_on_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.power_off_btn = ttk.Button(
            power_frame,
            text="Power OFF",
            command=lambda: self._set_power(False),
            state=tk.DISABLED
        )
        self.power_off_btn.pack(side=tk.LEFT)

        # Auto-connect setting
        auto_frame = ttk.LabelFrame(self, text="Auto Settings", padding="10")
        auto_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 10))

        self.auto_connect_var = tk.BooleanVar(
            value=self.config.get_setting('auto_connect', True)
        )
        ttk.Checkbutton(
            auto_frame,
            text="Auto-connect to last device on startup",
            variable=self.auto_connect_var,
            command=self._save_auto_settings
        ).pack(anchor=tk.W)

        self.restore_state_var = tk.BooleanVar(
            value=self.config.get_setting('restore_last_state', True)
        )
        ttk.Checkbutton(
            auto_frame,
            text="Restore last preset on startup",
            variable=self.restore_state_var,
            command=self._save_auto_settings
        ).pack(anchor=tk.W)

        # Sprite font library
        sprite_frame = ttk.LabelFrame(self, text="Sprite Fonts", padding="10")
        sprite_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        sprite_frame.columnconfigure(1, weight=1)

        # Font listbox
        self.sprite_font_listbox = tk.Listbox(sprite_frame, height=6)
        self.sprite_font_listbox.grid(row=0, column=0, rowspan=4, sticky=(tk.N, tk.S, tk.W))
        self.sprite_font_listbox.bind('<<ListboxSelect>>', self._on_sprite_font_select)

        list_scroll = ttk.Scrollbar(
            sprite_frame,
            orient=tk.VERTICAL,
            command=self.sprite_font_listbox.yview
        )
        list_scroll.grid(row=0, column=1, rowspan=4, sticky=(tk.N, tk.S))
        self.sprite_font_listbox.configure(yscrollcommand=list_scroll.set)

        # Font form
        form_frame = ttk.Frame(sprite_frame)
        form_frame.grid(row=0, column=2, rowspan=4, sticky=(tk.W, tk.E), padx=(10, 0))
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.sprite_font_name_var = tk.StringVar()
        ttk.Entry(
            form_frame,
            textvariable=self.sprite_font_name_var,
            width=24
        ).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(form_frame, text="Sprite Sheet:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.sprite_font_path_var = tk.StringVar()
        path_frame = ttk.Frame(form_frame)
        path_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Entry(
            path_frame,
            textvariable=self.sprite_font_path_var,
            width=18
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            path_frame,
            text="Browse",
            command=self._browse_sprite_font_file
        ).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(form_frame, text="Glyph order:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        # Default order with trailing space (73 chars to match cols=73)
        self.sprite_font_order_var = tk.StringVar(
            value='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$% '
        )
        ttk.Entry(
            form_frame,
            textvariable=self.sprite_font_order_var,
            width=24
        ).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(form_frame, text="Columns:").grid(row=3, column=0, sticky=tk.W)
        # Default cols=73 to match the 73-character glyph order
        self.sprite_font_cols_var = tk.IntVar(value=73)
        ttk.Spinbox(
            form_frame,
            from_=1,
            to=256,
            textvariable=self.sprite_font_cols_var,
            width=6
        ).grid(row=3, column=1, sticky=tk.W)

        # Font action buttons
        btn_frame = ttk.Frame(sprite_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        ttk.Button(btn_frame, text="Add", command=self._add_sprite_font).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Update", command=self._update_sprite_font).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Delete", command=self._delete_sprite_font).pack(side=tk.LEFT)

        # Initial refresh
        self._refresh_sprite_font_listbox()

    def _set_brightness(self) -> None:
        """Set device brightness."""
        if not self.state.is_connected:
            return

        brightness = self.brightness_var.get()

        def on_complete():
            pass

        def on_error(error):
            messagebox.showerror("Error", f"Failed to set brightness: {error}")

        self.device_manager.set_brightness(
            brightness,
            on_complete=on_complete,
            on_error=on_error
        )

    def _set_power(self, on: bool) -> None:
        """Set device power state."""
        if not self.state.is_connected:
            return

        def on_complete():
            pass

        def on_error(error):
            messagebox.showerror("Error", f"Failed to set power: {error}")

        self.device_manager.set_power(
            on,
            on_complete=on_complete,
            on_error=on_error
        )

    def _save_auto_settings(self) -> None:
        """Save auto-connect settings."""
        self.config.set_setting('auto_connect', self.auto_connect_var.get())
        self.config.set_setting('restore_last_state', self.restore_state_var.get())

    def _browse_sprite_font_file(self) -> None:
        """Browse for sprite font image file."""
        path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("PNG files", "*.png"),
                ("All files", "*.*")
            ],
            title="Select Sprite Font Image"
        )

        if path:
            self.sprite_font_path_var.set(path)

    def _on_sprite_font_select(self, event) -> None:
        """Handle sprite font listbox selection."""
        selection = self.sprite_font_listbox.curselection()
        if not selection:
            return

        fonts = self.config.get_sprite_fonts()
        if selection[0] < len(fonts):
            font = fonts[selection[0]]
            self.sprite_font_name_var.set(font.get('name', ''))
            self.sprite_font_path_var.set(font.get('path', ''))
            self.sprite_font_order_var.set(font.get('order', ''))
            self.sprite_font_cols_var.set(font.get('cols', 1))

    def _refresh_sprite_font_listbox(self) -> None:
        """Refresh the sprite font listbox."""
        self.sprite_font_listbox.delete(0, tk.END)
        fonts = self.config.get_sprite_fonts()

        for font in fonts:
            self.sprite_font_listbox.insert(tk.END, font.get('name', 'Unnamed'))

    def _add_sprite_font(self) -> None:
        """Add a new sprite font."""
        name = self.sprite_font_name_var.get().strip()
        path = self.sprite_font_path_var.get().strip()
        order = self.sprite_font_order_var.get()
        cols = self.sprite_font_cols_var.get()

        if not name:
            messagebox.showwarning("No Name", "Please enter a font name")
            return

        if not path:
            messagebox.showwarning("No Path", "Please select a sprite sheet image")
            return

        font = {
            'name': name,
            'path': path,
            'order': order,
            'cols': cols
        }

        self.config.add_sprite_font(font)
        self._refresh_sprite_font_listbox()
        self._notify_fonts_changed()

        # Clear form
        self.sprite_font_name_var.set('')
        self.sprite_font_path_var.set('')

    def _update_sprite_font(self) -> None:
        """Update the selected sprite font."""
        selection = self.sprite_font_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a font to update")
            return

        name = self.sprite_font_name_var.get().strip()
        path = self.sprite_font_path_var.get().strip()
        order = self.sprite_font_order_var.get()
        cols = self.sprite_font_cols_var.get()

        if not name:
            messagebox.showwarning("No Name", "Please enter a font name")
            return

        font = {
            'name': name,
            'path': path,
            'order': order,
            'cols': cols
        }

        self.config.update_sprite_font(selection[0], font)
        self._refresh_sprite_font_listbox()
        self._notify_fonts_changed()

    def _delete_sprite_font(self) -> None:
        """Delete the selected sprite font."""
        selection = self.sprite_font_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a font to delete")
            return

        if messagebox.askyesno("Confirm", "Delete this sprite font?"):
            self.config.remove_sprite_font(selection[0])
            self._refresh_sprite_font_listbox()
            self._notify_fonts_changed()

            # Clear form
            self.sprite_font_name_var.set('')
            self.sprite_font_path_var.set('')

    def _notify_fonts_changed(self) -> None:
        """Notify listeners that sprite fonts have changed."""
        if self.on_sprite_fonts_changed:
            self.on_sprite_fonts_changed()

    def on_connected(self) -> None:
        """Called when device is connected."""
        self.set_brightness_btn.config(state=tk.NORMAL)
        self.power_on_btn.config(state=tk.NORMAL)
        self.power_off_btn.config(state=tk.NORMAL)

    def on_disconnected(self) -> None:
        """Called when device is disconnected."""
        self.set_brightness_btn.config(state=tk.DISABLED)
        self.power_on_btn.config(state=tk.DISABLED)
        self.power_off_btn.config(state=tk.DISABLED)
