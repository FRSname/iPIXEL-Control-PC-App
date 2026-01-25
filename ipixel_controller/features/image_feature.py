"""
Image display feature.

Allows loading and displaying images on the LED panel.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Any, Optional
from PIL import Image, ImageTk

from .base import FeatureBase
from ..utils.paths import resolve_asset_path, is_valid_image_path
from ..utils.image_utils import generate_thumbnail, resize_to_display


class ImageFeature(FeatureBase):
    """
    Image display feature.

    Allows users to load images from disk and display them on the LED panel.
    Supports PNG, JPG, GIF, and BMP formats.
    """

    feature_id = "image"
    display_name = "Image"
    tab_icon = "🖼️"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_path: Optional[str] = None
        self.preview_image: Optional[ImageTk.PhotoImage] = None

    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """Create the image tab UI."""
        self.tab_frame = ttk.Frame(notebook, padding="10")
        notebook.add(self.tab_frame, text=self.tab_title)

        # Info label
        info = self._create_info_label(
            self.tab_frame,
            "Load and display images on your LED panel.\n"
            "Supported formats: PNG, JPG, GIF, BMP"
        )
        info.pack(anchor=tk.W, pady=(0, 10))

        # Preview frame
        preview_frame = ttk.LabelFrame(self.tab_frame, text="Preview", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.preview_label = ttk.Label(preview_frame, text="No image loaded")
        self.preview_label.pack(expand=True)

        # Path display
        path_frame = ttk.Frame(self.tab_frame)
        path_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(path_frame, text="Path:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value="No image selected")
        ttk.Label(
            path_frame,
            textvariable=self.path_var,
            foreground="gray"
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Buttons
        button_frame = ttk.Frame(self.tab_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(
            button_frame,
            text="Load Image",
            command=self._load_image
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.send_button = self._create_send_button(button_frame, "Send Image")
        self.send_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Save as Preset",
            command=self._save_preset
        ).pack(side=tk.LEFT)

        return self.tab_frame

    def _load_image(self) -> None:
        """Open file dialog to load an image."""
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg *.jpeg"),
            ("GIF files", "*.gif"),
            ("BMP files", "*.bmp"),
            ("All files", "*.*")
        ]

        path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=filetypes
        )

        if path:
            self._set_image(path)

    def _set_image(self, path: str) -> None:
        """Set the current image and update preview."""
        resolved_path = resolve_asset_path(path)

        if not is_valid_image_path(resolved_path):
            messagebox.showerror("Error", f"Invalid image file: {path}")
            return

        self.image_path = path
        self.path_var.set(os.path.basename(path))

        # Update preview
        try:
            thumbnail = generate_thumbnail(resolved_path, (256, 64))
            if thumbnail:
                self.preview_image = ImageTk.PhotoImage(thumbnail)
                self.preview_label.config(image=self.preview_image, text="")
            else:
                self.preview_label.config(image="", text="Preview unavailable")
        except Exception as e:
            self.preview_label.config(image="", text=f"Preview error: {e}")

    def send_to_display(self) -> bool:
        """Send the loaded image to the display."""
        if not self.require_connection():
            return False

        if not self.image_path:
            messagebox.showwarning("No Image", "Please load an image first.")
            return False

        resolved_path = resolve_asset_path(self.image_path)
        if not is_valid_image_path(resolved_path):
            messagebox.showerror("Error", "Image file not found.")
            return False

        # Stop other displays
        self.stop_other_features()
        self.set_active()

        # Send image
        def on_complete():
            pass  # Success

        def on_error(error):
            messagebox.showerror("Error", f"Failed to send image: {error}")

        self.device.send_image(
            resolved_path,
            on_complete=on_complete,
            on_error=on_error,
            resize_method='crop',
            save_slot=0
        )

        return True

    def stop(self) -> None:
        """Stop any running operations."""
        # Image feature has no timers
        pass

    def _save_preset(self) -> None:
        """Save current image as preset."""
        if not self.image_path:
            messagebox.showwarning("No Image", "Please load an image first.")
            return

        from ..ui.widgets.preset_dialog import PresetSaveDialog

        def create_preset(name: str) -> Dict[str, Any]:
            return self.create_preset(name)

        def on_complete(preset: Dict[str, Any]):
            self.config.add_preset(preset)
            messagebox.showinfo("Saved", f"Preset '{preset['name']}' saved!")

        PresetSaveDialog(
            parent=self.root,
            preset_type="Image",
            default_name=os.path.basename(self.image_path or "Image"),
            on_create=create_preset,
            on_complete=on_complete
        )

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Create a preset from current state."""
        preset = {
            'name': name,
            'type': self.feature_id,
            'image_path': self.image_path,
        }

        # Generate thumbnail for preset preview
        if self.image_path:
            resolved = resolve_asset_path(self.image_path)
            thumb = generate_thumbnail(resolved, (64, 16))
            if thumb:
                from ..utils.image_utils import image_to_base64
                preset['thumbnail'] = image_to_base64(thumb)

        return preset

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute a saved preset."""
        image_path = preset.get('image_path')
        if image_path:
            self._set_image(image_path)
            return self.send_to_display()
        return False

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """Get preview text for preset."""
        path = preset.get('image_path', '')
        return os.path.basename(path) if path else "Unknown"

    def get_preset_details(self, preset: Dict[str, Any]) -> str:
        """Get detailed description for preset."""
        path = preset.get('image_path', 'Unknown')
        return f"Image: {path}"
