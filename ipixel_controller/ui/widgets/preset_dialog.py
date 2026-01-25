"""
Reusable preset save dialog.

Replaces the 4+ duplicate preset save dialog implementations in the original
code with a single reusable component.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Any, Optional


class PresetSaveDialog:
    """
    Reusable preset save dialog.

    Features:
    - Modal dialog for entering preset name
    - Validation of preset name
    - Callback to generate preset data from name
    - Callback when save is complete

    Usage:
        def create_preset(name: str) -> Dict:
            return {
                "name": name,
                "type": "stock",
                "ticker": "AAPL",
                ...
            }

        def on_saved(preset: Dict):
            presets.append(preset)
            save_presets()

        PresetSaveDialog(
            parent=root,
            preset_type="Stock",
            default_name="My Stock Preset",
            on_create=create_preset,
            on_complete=on_saved
        )
    """

    def __init__(
        self,
        parent: tk.Tk,
        preset_type: str,
        default_name: str = "",
        on_create: Optional[Callable[[str], Dict[str, Any]]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        title: Optional[str] = None,
        width: int = 400,
        height: int = 120
    ):
        """
        Initialize and show the preset save dialog.

        Args:
            parent: Parent window
            preset_type: Type of preset (e.g., "Stock", "Weather")
            default_name: Default preset name
            on_create: Callback to create preset dict from name
            on_complete: Callback when preset is saved
            title: Dialog title (defaults to "Save {preset_type} Preset")
            width: Dialog width
            height: Dialog height
        """
        self.parent = parent
        self.preset_type = preset_type
        self.on_create = on_create
        self.on_complete = on_complete

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title or f"Save {preset_type} Preset")
        self.dialog.geometry(f"{width}x{height}")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on parent
        self._center_on_parent(width, height)

        # Create UI
        self._create_ui(default_name)

    def _center_on_parent(self, width: int, height: int) -> None:
        """Center dialog on parent window."""
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

    def _create_ui(self, default_name: str) -> None:
        """Create the dialog UI."""
        # Main frame
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Name label and entry
        ttk.Label(frame, text="Preset Name:").pack(anchor=tk.W)

        self.name_entry = ttk.Entry(frame, width=40)
        self.name_entry.pack(fill=tk.X, pady=(5, 15))
        self.name_entry.insert(0, default_name)
        self.name_entry.focus()
        self.name_entry.select_range(0, tk.END)

        # Bind Enter key
        self.name_entry.bind('<Return>', lambda e: self._save())
        self.dialog.bind('<Escape>', lambda e: self._cancel())

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Save",
            command=self._save
        ).pack(side=tk.RIGHT)

    def _save(self) -> None:
        """Handle save button click."""
        name = self.name_entry.get().strip()

        if not name:
            messagebox.showwarning(
                "No Name",
                "Please enter a preset name.",
                parent=self.dialog
            )
            return

        # Create preset
        if self.on_create:
            try:
                preset = self.on_create(name)
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Failed to create preset: {e}",
                    parent=self.dialog
                )
                return
        else:
            preset = {"name": name, "type": self.preset_type.lower()}

        # Complete
        self.dialog.destroy()

        if self.on_complete:
            self.on_complete(preset)

    def _cancel(self) -> None:
        """Handle cancel button click."""
        self.dialog.destroy()


class PresetConfirmDialog:
    """
    Confirmation dialog for preset operations (delete, overwrite, etc.).

    Usage:
        PresetConfirmDialog(
            parent=root,
            title="Delete Preset",
            message="Are you sure you want to delete 'My Preset'?",
            on_confirm=lambda: delete_preset(preset),
            confirm_text="Delete",
            is_destructive=True
        )
    """

    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        message: str,
        on_confirm: Callable[[], None],
        on_cancel: Optional[Callable[[], None]] = None,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        is_destructive: bool = False
    ):
        """
        Initialize and show the confirmation dialog.

        Args:
            parent: Parent window
            title: Dialog title
            message: Message to display
            on_confirm: Callback when confirmed
            on_cancel: Callback when cancelled
            confirm_text: Text for confirm button
            cancel_text: Text for cancel button
            is_destructive: If True, use warning style
        """
        if is_destructive:
            result = messagebox.askyesno(title, message, icon='warning', parent=parent)
        else:
            result = messagebox.askyesno(title, message, parent=parent)

        if result:
            on_confirm()
        elif on_cancel:
            on_cancel()
