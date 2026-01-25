"""
Reusable sprite font selector widget.

Replaces the 4 duplicate sprite font selector implementations in the original
code with a single reusable component.
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Callable, Optional


class SpriteFontSelector(ttk.Frame):
    """
    Reusable sprite font selector with optional enable checkbox and dropdown.

    Features:
    - Optional checkbox to enable/disable sprite font usage
    - Dropdown to select from available fonts
    - Callback when selection changes
    - Easy to update font list dynamically

    Usage:
        use_sprite = tk.BooleanVar(value=True)
        font_name = tk.StringVar(value="Default")

        selector = SpriteFontSelector(
            parent,
            font_names=["Default", "Clock", "Large"],
            use_sprite_var=use_sprite,
            font_name_var=font_name,
            on_change=lambda: print("Font changed!")
        )
    """

    def __init__(
        self,
        parent: tk.Widget,
        font_names: List[str],
        use_sprite_var: Optional[tk.BooleanVar] = None,
        font_name_var: Optional[tk.StringVar] = None,
        on_change: Optional[Callable[[], None]] = None,
        show_checkbox: bool = True,
        checkbox_label: str = "Use sprite font",
        font_label: str = "Font:",
        **kwargs
    ):
        """
        Initialize the sprite font selector.

        Args:
            parent: Parent widget
            font_names: List of available font names
            use_sprite_var: BooleanVar for checkbox state (optional)
            font_name_var: StringVar for selected font name (optional)
            on_change: Callback when selection changes
            show_checkbox: Whether to show the enable checkbox
            checkbox_label: Label for the checkbox
            font_label: Label for the font dropdown
            **kwargs: Additional arguments passed to ttk.Frame
        """
        super().__init__(parent, **kwargs)

        self._on_change = on_change

        # Create variables if not provided
        self._use_sprite_var = use_sprite_var or tk.BooleanVar(value=True)
        self._font_name_var = font_name_var or tk.StringVar(value=font_names[0] if font_names else "")

        row = 0

        # Checkbox for enabling sprite font
        if show_checkbox:
            self._checkbox = ttk.Checkbutton(
                self,
                text=checkbox_label,
                variable=self._use_sprite_var,
                command=self._on_checkbox_change
            )
            self._checkbox.grid(row=row, column=0, columnspan=2, sticky=tk.W)
            row += 1

        # Font label and dropdown
        ttk.Label(self, text=font_label).grid(
            row=row, column=0, sticky=tk.W, pady=(5, 0)
        )

        self._combo = ttk.Combobox(
            self,
            textvariable=self._font_name_var,
            values=font_names,
            state="readonly",
            width=20
        )
        self._combo.grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0)
        )
        self._combo.bind('<<ComboboxSelected>>', self._on_combo_change)

        # Configure grid
        self.columnconfigure(1, weight=1)

        # Update combo state based on checkbox
        self._update_combo_state()

    def _on_checkbox_change(self) -> None:
        """Handle checkbox state change."""
        self._update_combo_state()
        self._notify_change()

    def _on_combo_change(self, event=None) -> None:
        """Handle combobox selection change."""
        self._notify_change()

    def _update_combo_state(self) -> None:
        """Enable/disable combo based on checkbox."""
        if self._use_sprite_var.get():
            self._combo.state(['!disabled'])
        else:
            self._combo.state(['disabled'])

    def _notify_change(self) -> None:
        """Notify callback of change."""
        if self._on_change:
            self._on_change()

    def update_fonts(self, font_names: List[str]) -> None:
        """
        Update the list of available fonts.

        Args:
            font_names: New list of font names
        """
        current = self._font_name_var.get()
        self._combo['values'] = font_names

        # Keep current selection if still valid
        if current not in font_names and font_names:
            self._font_name_var.set(font_names[0])

    @property
    def use_sprite(self) -> bool:
        """Whether sprite font is enabled."""
        return self._use_sprite_var.get()

    @use_sprite.setter
    def use_sprite(self, value: bool) -> None:
        """Set sprite font enabled state."""
        self._use_sprite_var.set(value)
        self._update_combo_state()

    @property
    def font_name(self) -> str:
        """Selected font name."""
        return self._font_name_var.get()

    @font_name.setter
    def font_name(self, value: str) -> None:
        """Set selected font name."""
        self._font_name_var.set(value)

    @property
    def use_sprite_var(self) -> tk.BooleanVar:
        """Get the BooleanVar for checkbox."""
        return self._use_sprite_var

    @property
    def font_name_var(self) -> tk.StringVar:
        """Get the StringVar for font name."""
        return self._font_name_var
