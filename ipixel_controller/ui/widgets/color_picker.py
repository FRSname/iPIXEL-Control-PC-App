"""
Reusable color picker widget.

Replaces the 12+ duplicate color picker implementations in the original code
with a single reusable component.
"""

import tkinter as tk
from tkinter import ttk, colorchooser
from typing import Callable, Optional


class ColorPickerWidget(ttk.Frame):
    """
    Reusable color picker widget with preview canvas and choose button.

    Features:
    - Label describing the color purpose
    - Preview canvas showing current color
    - Choose button to open color picker dialog
    - Optional callback when color changes

    Usage:
        picker = ColorPickerWidget(
            parent,
            label="Text Color:",
            initial_color="#FFFFFF",
            on_change=lambda color: print(f"New color: {color}")
        )
        picker.pack()

        # Get current color
        current = picker.get_color()

        # Set color programmatically
        picker.set_color("#FF0000")
    """

    def __init__(
        self,
        parent: tk.Widget,
        label: str = "Color:",
        initial_color: str = "#FFFFFF",
        on_change: Optional[Callable[[str], None]] = None,
        canvas_width: int = 30,
        canvas_height: int = 20,
        dialog_title: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the color picker widget.

        Args:
            parent: Parent widget
            label: Label text to display
            initial_color: Initial color value (hex string)
            on_change: Callback when color changes, receives new color string
            canvas_width: Width of the color preview canvas
            canvas_height: Height of the color preview canvas
            dialog_title: Title for the color picker dialog
            **kwargs: Additional arguments passed to ttk.Frame
        """
        super().__init__(parent, **kwargs)

        self._color = initial_color
        self._on_change = on_change
        self._dialog_title = dialog_title or f"Choose {label.rstrip(':')}"

        # Create widgets
        if label:
            ttk.Label(self, text=label).pack(side=tk.LEFT, padx=(0, 5))

        self._canvas = tk.Canvas(
            self,
            width=canvas_width,
            height=canvas_height,
            bg=self._color,
            relief=tk.SUNKEN,
            highlightthickness=1
        )
        self._canvas.pack(side=tk.LEFT, padx=(0, 5))

        # Make canvas clickable too
        self._canvas.bind('<Button-1>', lambda e: self._choose_color())

        ttk.Button(
            self,
            text="Choose",
            command=self._choose_color
        ).pack(side=tk.LEFT)

    def _choose_color(self) -> None:
        """Open color chooser dialog."""
        result = colorchooser.askcolor(
            initialcolor=self._color,
            title=self._dialog_title
        )
        if result[1]:  # result is ((r, g, b), "#hexcolor")
            self.set_color(result[1])

    def set_color(self, color: str) -> None:
        """
        Set the color programmatically.

        Args:
            color: Hex color string (e.g., "#FFFFFF")
        """
        old_color = self._color
        self._color = color
        self._canvas.config(bg=self._color)

        # Notify callback if color actually changed
        if self._on_change and color != old_color:
            self._on_change(self._color)

    def get_color(self) -> str:
        """
        Get the current color.

        Returns:
            Hex color string
        """
        return self._color

    # Property for convenient access
    @property
    def color(self) -> str:
        """Current color value."""
        return self._color

    @color.setter
    def color(self, value: str) -> None:
        """Set color value."""
        self.set_color(value)


class DualColorPickerWidget(ttk.Frame):
    """
    Widget with two color pickers - text color and background color.

    Common pattern in the app where both text and background colors are needed.

    Usage:
        dual_picker = DualColorPickerWidget(
            parent,
            text_color="#FFFFFF",
            bg_color="#000000",
            on_text_change=lambda c: print(f"Text: {c}"),
            on_bg_change=lambda c: print(f"BG: {c}")
        )
    """

    def __init__(
        self,
        parent: tk.Widget,
        text_label: str = "Text Color:",
        bg_label: str = "Background:",
        text_color: str = "#FFFFFF",
        bg_color: str = "#000000",
        on_text_change: Optional[Callable[[str], None]] = None,
        on_bg_change: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        """
        Initialize dual color picker.

        Args:
            parent: Parent widget
            text_label: Label for text color picker
            bg_label: Label for background color picker
            text_color: Initial text color
            bg_color: Initial background color
            on_text_change: Callback for text color changes
            on_bg_change: Callback for background color changes
        """
        super().__init__(parent, **kwargs)

        self.text_picker = ColorPickerWidget(
            self,
            label=text_label,
            initial_color=text_color,
            on_change=on_text_change
        )
        self.text_picker.pack(side=tk.LEFT, padx=(0, 15))

        self.bg_picker = ColorPickerWidget(
            self,
            label=bg_label,
            initial_color=bg_color,
            on_change=on_bg_change
        )
        self.bg_picker.pack(side=tk.LEFT)

    @property
    def text_color(self) -> str:
        """Get text color."""
        return self.text_picker.get_color()

    @text_color.setter
    def text_color(self, value: str) -> None:
        """Set text color."""
        self.text_picker.set_color(value)

    @property
    def bg_color(self) -> str:
        """Get background color."""
        return self.bg_picker.get_color()

    @bg_color.setter
    def bg_color(self, value: str) -> None:
        """Set background color."""
        self.bg_picker.set_color(value)
