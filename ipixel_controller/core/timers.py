"""
Centralized timer management.

TimerManager solves the problem of 12+ scattered timer variables in the
original code by providing a single point of control for all recurring tasks.
"""

from typing import Dict, Optional, Callable, Set
import tkinter as tk


class TimerNames:
    """
    Constants for timer names.

    Using constants prevents typos and makes it easy to find all timer usages.
    """
    # Clock timers
    CLOCK_UPDATE = "clock_update"
    COUNTDOWN_UPDATE = "countdown_update"
    COUNTDOWN_STATIC = "countdown_static"

    # Stock timers
    STOCK_REFRESH = "stock_refresh"
    STOCK_STATIC_CYCLE = "stock_static_cycle"

    # YouTube timers
    YOUTUBE_REFRESH = "youtube_refresh"
    YOUTUBE_LOGO_DELAY = "youtube_logo_delay"

    # Weather timers
    WEATHER_REFRESH = "weather_refresh"

    # Animation timers
    ANIMATION_FRAME = "animation_frame"

    # Text/Sprite timers
    SPRITE_SCROLL = "sprite_scroll"
    TEXT_STATIC_CYCLE = "text_static_cycle"

    # Teams timers
    TEAMS_CHECK = "teams_check"

    # Playlist timers
    PLAYLIST_NEXT = "playlist_next"


class TimerManager:
    """
    Centralized timer management.

    All timers registered here can be tracked, cancelled individually,
    or cancelled all at once. This replaces the 12+ scattered timer
    variables in the original code.

    Features:
    - Auto-cancels existing timer when scheduling with same name
    - Cancel by name, prefix, or all at once
    - Check if specific timer is active
    - Debug logging of active timers

    Usage:
        timers = TimerManager(root)
        timers.schedule("clock_update", 1000, update_clock)
        timers.cancel("clock_update")
        timers.cancel_by_prefix("stock_")
        timers.cancel_all()
    """

    def __init__(self, root: tk.Tk):
        """
        Initialize the timer manager.

        Args:
            root: Tkinter root window for scheduling after() calls
        """
        self._root = root
        self._timers: Dict[str, str] = {}  # name -> after_id

    def schedule(self, name: str, delay_ms: int, callback: Callable) -> str:
        """
        Schedule a timer, automatically cancelling any existing timer with same name.

        Args:
            name: Unique name for this timer (use TimerNames constants)
            delay_ms: Delay in milliseconds before callback is executed
            callback: Function to call when timer fires

        Returns:
            The after_id for the scheduled timer
        """
        # Cancel any existing timer with this name
        self.cancel(name)

        # Schedule new timer
        after_id = self._root.after(delay_ms, callback)
        self._timers[name] = after_id
        return after_id

    def schedule_repeating(
        self,
        name: str,
        interval_ms: int,
        callback: Callable[[], bool]
    ) -> str:
        """
        Schedule a repeating timer.

        Args:
            name: Unique name for this timer
            interval_ms: Interval in milliseconds between calls
            callback: Function to call. Should return True to continue,
                     False to stop.

        Returns:
            The after_id for the first scheduled callback
        """
        def tick():
            if name not in self._timers:
                return  # Timer was cancelled

            should_continue = callback()
            if should_continue and name in self._timers:
                # Reschedule
                after_id = self._root.after(interval_ms, tick)
                self._timers[name] = after_id
            else:
                # Remove from tracking
                self._timers.pop(name, None)

        return self.schedule(name, interval_ms, tick)

    def cancel(self, name: str) -> bool:
        """
        Cancel a specific timer by name.

        Args:
            name: Name of the timer to cancel

        Returns:
            True if timer was found and cancelled, False otherwise
        """
        if name in self._timers:
            try:
                self._root.after_cancel(self._timers[name])
            except tk.TclError:
                pass  # Timer already expired
            del self._timers[name]
            return True
        return False

    def cancel_all(self) -> int:
        """
        Cancel all active timers.

        Returns:
            Number of timers cancelled
        """
        count = len(self._timers)
        for after_id in self._timers.values():
            try:
                self._root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._timers.clear()
        return count

    def cancel_by_prefix(self, prefix: str) -> int:
        """
        Cancel all timers whose names start with the given prefix.

        Useful for cancelling all timers for a specific feature, e.g.,
        cancel_by_prefix("stock_") to stop all stock-related timers.

        Args:
            prefix: Prefix to match against timer names

        Returns:
            Number of timers cancelled
        """
        names_to_cancel = [n for n in self._timers if n.startswith(prefix)]
        for name in names_to_cancel:
            self.cancel(name)
        return len(names_to_cancel)

    def cancel_display_timers(self) -> int:
        """
        Cancel all display-related timers.

        This is called before sending new content to ensure old timers
        don't interfere. Equivalent to _stop_active_display_tasks() in
        the original code.

        Returns:
            Number of timers cancelled
        """
        display_timers = [
            TimerNames.CLOCK_UPDATE,
            TimerNames.COUNTDOWN_UPDATE,
            TimerNames.COUNTDOWN_STATIC,
            TimerNames.STOCK_REFRESH,
            TimerNames.STOCK_STATIC_CYCLE,
            TimerNames.YOUTUBE_REFRESH,
            TimerNames.YOUTUBE_LOGO_DELAY,
            TimerNames.WEATHER_REFRESH,
            TimerNames.ANIMATION_FRAME,
            TimerNames.SPRITE_SCROLL,
            TimerNames.TEXT_STATIC_CYCLE,
        ]
        count = 0
        for name in display_timers:
            if self.cancel(name):
                count += 1
        return count

    def is_active(self, name: str) -> bool:
        """
        Check if a timer with the given name is currently active.

        Args:
            name: Timer name to check

        Returns:
            True if timer is active, False otherwise
        """
        return name in self._timers

    def get_active_timers(self) -> Set[str]:
        """
        Get the names of all currently active timers.

        Returns:
            Set of active timer names
        """
        return set(self._timers.keys())

    def __len__(self) -> int:
        """Return number of active timers."""
        return len(self._timers)

    def __contains__(self, name: str) -> bool:
        """Check if timer name is active."""
        return name in self._timers
