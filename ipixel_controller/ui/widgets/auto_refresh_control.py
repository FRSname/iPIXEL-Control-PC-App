"""
Reusable auto-refresh control widget.

Replaces the 3 duplicate auto-refresh implementations in the original code
(Stock, YouTube, Weather tabs) with a single reusable component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class AutoRefreshControl(ttk.Frame):
    """
    Reusable auto-refresh control with enable checkbox and interval selector.

    Features:
    - Checkbox to enable/disable auto-refresh
    - Spinbox to set refresh interval
    - Configurable interval range and step
    - Callback when settings change

    Usage:
        control = AutoRefreshControl(
            parent,
            enabled_var=tk.BooleanVar(value=False),
            interval_var=tk.IntVar(value=60),
            min_interval=30,
            max_interval=300,
            on_change=lambda: print("Settings changed")
        )
    """

    def __init__(
        self,
        parent: tk.Widget,
        enabled_var: Optional[tk.BooleanVar] = None,
        interval_var: Optional[tk.IntVar] = None,
        min_interval: int = 30,
        max_interval: int = 300,
        interval_step: int = 30,
        default_interval: int = 60,
        label: str = "Enable auto-refresh every",
        unit_label: str = "seconds",
        on_change: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        """
        Initialize the auto-refresh control.

        Args:
            parent: Parent widget
            enabled_var: BooleanVar for enabled state (optional)
            interval_var: IntVar for interval value (optional)
            min_interval: Minimum refresh interval in seconds
            max_interval: Maximum refresh interval in seconds
            interval_step: Step size for spinbox
            default_interval: Default interval value
            label: Label for the checkbox
            unit_label: Label for the unit (e.g., "seconds")
            on_change: Callback when settings change
            **kwargs: Additional arguments passed to ttk.Frame
        """
        super().__init__(parent, **kwargs)

        self._on_change = on_change

        # Create variables if not provided
        self._enabled_var = enabled_var or tk.BooleanVar(value=False)
        self._interval_var = interval_var or tk.IntVar(value=default_interval)

        # Checkbox
        self._checkbox = ttk.Checkbutton(
            self,
            text=label,
            variable=self._enabled_var,
            command=self._on_checkbox_change
        )
        self._checkbox.pack(side=tk.LEFT, padx=(0, 5))

        # Interval spinbox
        self._spinbox = ttk.Spinbox(
            self,
            from_=min_interval,
            to=max_interval,
            increment=interval_step,
            textvariable=self._interval_var,
            width=5,
            command=self._notify_change
        )
        self._spinbox.pack(side=tk.LEFT, padx=(0, 5))

        # Bind spinbox change events
        self._spinbox.bind('<Return>', lambda e: self._notify_change())
        self._spinbox.bind('<FocusOut>', lambda e: self._notify_change())

        # Unit label
        ttk.Label(self, text=unit_label).pack(side=tk.LEFT)

        # Update spinbox state
        self._update_spinbox_state()

    def _on_checkbox_change(self) -> None:
        """Handle checkbox state change."""
        self._update_spinbox_state()
        self._notify_change()

    def _update_spinbox_state(self) -> None:
        """Enable/disable spinbox based on checkbox."""
        if self._enabled_var.get():
            self._spinbox.state(['!disabled'])
        else:
            self._spinbox.state(['disabled'])

    def _notify_change(self) -> None:
        """Notify callback of change."""
        if self._on_change:
            self._on_change()

    @property
    def enabled(self) -> bool:
        """Whether auto-refresh is enabled."""
        return self._enabled_var.get()

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set enabled state."""
        self._enabled_var.set(value)
        self._update_spinbox_state()

    @property
    def interval(self) -> int:
        """Refresh interval in seconds."""
        return self._interval_var.get()

    @interval.setter
    def interval(self, value: int) -> None:
        """Set refresh interval."""
        self._interval_var.set(value)

    @property
    def interval_ms(self) -> int:
        """Refresh interval in milliseconds."""
        return self._interval_var.get() * 1000

    @property
    def enabled_var(self) -> tk.BooleanVar:
        """Get the BooleanVar for enabled state."""
        return self._enabled_var

    @property
    def interval_var(self) -> tk.IntVar:
        """Get the IntVar for interval."""
        return self._interval_var

    def start_if_enabled(self, callback: Callable[[], None], timer_manager=None, timer_name: str = None) -> Optional[str]:
        """
        Start auto-refresh if enabled.

        Args:
            callback: Function to call on each refresh
            timer_manager: Optional TimerManager to use
            timer_name: Timer name for TimerManager

        Returns:
            Timer ID if started, None if not enabled
        """
        if not self.enabled:
            return None

        if timer_manager and timer_name:
            return timer_manager.schedule(timer_name, self.interval_ms, callback)
        return None
