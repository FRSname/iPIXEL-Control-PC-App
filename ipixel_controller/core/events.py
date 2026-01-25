"""
Event bus for component communication.

The EventBus enables loose coupling between components by allowing them
to communicate through events rather than direct method calls.
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class Events:
    """
    Event name constants.

    Using constants prevents typos and makes it easy to find all event usages.
    """
    # Connection events
    CONNECTION_CHANGED = "connection_changed"
    DEVICE_SCANNING = "device_scanning"
    DEVICE_SCAN_COMPLETE = "device_scan_complete"

    # Display events
    FEATURE_ACTIVATED = "feature_activated"
    DISPLAY_CONTENT_SENT = "display_content_sent"
    DISPLAY_CLEARED = "display_cleared"

    # Preset events
    PRESET_EXECUTED = "preset_executed"
    PRESET_SAVED = "preset_saved"
    PRESET_DELETED = "preset_deleted"
    PRESETS_CHANGED = "presets_changed"

    # Playlist events
    PLAYLIST_STARTED = "playlist_started"
    PLAYLIST_STOPPED = "playlist_stopped"
    PLAYLIST_PAUSED = "playlist_paused"
    PLAYLIST_ITEM_CHANGED = "playlist_item_changed"

    # Data fetch events
    STOCK_DATA_FETCHED = "stock_data_fetched"
    YOUTUBE_DATA_FETCHED = "youtube_data_fetched"
    WEATHER_DATA_FETCHED = "weather_data_fetched"

    # Settings events
    SETTINGS_CHANGED = "settings_changed"
    SPRITE_FONTS_CHANGED = "sprite_fonts_changed"

    # Error events
    ERROR_OCCURRED = "error_occurred"
    WARNING_OCCURRED = "warning_occurred"


@dataclass
class EventData:
    """
    Wrapper for event data with metadata.

    Provides a consistent structure for event payloads.
    """
    event: str
    data: Any
    source: Optional[str] = None


class EventBus:
    """
    Pub/sub event system for component communication.

    Features:
    - Subscribe to events with callbacks
    - Publish events with optional data
    - Unsubscribe from events
    - Priority-based callback ordering
    - Optional async event handling

    Usage:
        bus = EventBus()

        # Subscribe
        def on_connected(data):
            print(f"Connected: {data}")
        bus.subscribe(Events.CONNECTION_CHANGED, on_connected)

        # Publish
        bus.publish(Events.CONNECTION_CHANGED, {"connected": True})

        # Unsubscribe
        bus.unsubscribe(Events.CONNECTION_CHANGED, on_connected)
    """

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: Dict[str, List[Callable]] = {}
        self._once_subscribers: Dict[str, List[Callable]] = {}

    def subscribe(
        self,
        event: str,
        callback: Callable[[Any], None],
        priority: int = 0
    ) -> None:
        """
        Subscribe to an event.

        Args:
            event: Event name to subscribe to (use Events constants)
            callback: Function to call when event is published.
                     Receives the event data as argument.
            priority: Higher priority callbacks are called first (default 0)
        """
        if event not in self._subscribers:
            self._subscribers[event] = []

        # Store as (priority, callback) tuple for ordering
        self._subscribers[event].append((priority, callback))
        # Sort by priority (descending)
        self._subscribers[event].sort(key=lambda x: -x[0])

    def subscribe_once(
        self,
        event: str,
        callback: Callable[[Any], None]
    ) -> None:
        """
        Subscribe to an event for a single occurrence only.

        The callback will be automatically unsubscribed after being called once.

        Args:
            event: Event name to subscribe to
            callback: Function to call once when event is published
        """
        if event not in self._once_subscribers:
            self._once_subscribers[event] = []
        self._once_subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> bool:
        """
        Unsubscribe a callback from an event.

        Args:
            event: Event name
            callback: The callback to remove

        Returns:
            True if callback was found and removed, False otherwise
        """
        if event in self._subscribers:
            original_len = len(self._subscribers[event])
            self._subscribers[event] = [
                (p, c) for p, c in self._subscribers[event] if c != callback
            ]
            if len(self._subscribers[event]) < original_len:
                return True

        if event in self._once_subscribers:
            if callback in self._once_subscribers[event]:
                self._once_subscribers[event].remove(callback)
                return True

        return False

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish an event to all subscribers.

        Args:
            event: Event name to publish
            data: Optional data to pass to callbacks

        Returns:
            Number of callbacks that were called
        """
        count = 0

        # Call regular subscribers
        if event in self._subscribers:
            for priority, callback in self._subscribers[event]:
                try:
                    callback(data)
                    count += 1
                except Exception as e:
                    logger.error(f"Error in event handler for {event}: {e}")

        # Call and remove once subscribers
        if event in self._once_subscribers:
            callbacks = self._once_subscribers.pop(event, [])
            for callback in callbacks:
                try:
                    callback(data)
                    count += 1
                except Exception as e:
                    logger.error(f"Error in once handler for {event}: {e}")

        return count

    def clear(self, event: Optional[str] = None) -> None:
        """
        Clear all subscribers for an event, or all events if none specified.

        Args:
            event: Event to clear, or None to clear all
        """
        if event is None:
            self._subscribers.clear()
            self._once_subscribers.clear()
        else:
            self._subscribers.pop(event, None)
            self._once_subscribers.pop(event, None)

    def has_subscribers(self, event: str) -> bool:
        """
        Check if an event has any subscribers.

        Args:
            event: Event name to check

        Returns:
            True if event has subscribers
        """
        regular = len(self._subscribers.get(event, []))
        once = len(self._once_subscribers.get(event, []))
        return (regular + once) > 0

    def subscriber_count(self, event: str) -> int:
        """
        Get the number of subscribers for an event.

        Args:
            event: Event name

        Returns:
            Number of subscribers
        """
        regular = len(self._subscribers.get(event, []))
        once = len(self._once_subscribers.get(event, []))
        return regular + once


# Global event bus instance (optional singleton pattern)
_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Get the global event bus instance.

    Creates one if it doesn't exist.
    """
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus
