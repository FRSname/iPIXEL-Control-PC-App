"""
Base class for feature plugins.

All display features (Text, Image, Clock, Stock, etc.) inherit from FeatureBase,
which provides common functionality and a consistent interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
import tkinter as tk
from tkinter import ttk, messagebox

if TYPE_CHECKING:
    from ..core.state import AppState
    from ..core.timers import TimerManager
    from ..core.events import EventBus


class FeatureBase(ABC):
    """
    Abstract base class for all display features.

    Each feature handles its own UI, state, and display logic.
    Features are self-contained plugins that can be enabled/disabled
    and loaded dynamically.

    Subclasses must implement:
    - feature_id: Unique identifier (e.g., "stock", "weather")
    - display_name: Human-readable name (e.g., "Stock Market")
    - tab_icon: Optional icon for tab (e.g., "📈")
    - create_tab(): Build the feature's UI
    - send_to_display(): Send content to the LED panel
    - stop(): Stop any running timers/animations
    - create_preset(): Create a preset from current state
    - execute_preset(): Execute a saved preset
    """

    # Feature metadata - override in subclasses
    feature_id: str = "base"
    display_name: str = "Base Feature"
    tab_icon: str = ""

    def __init__(
        self,
        root: tk.Tk,
        state: 'AppState',
        timers: 'TimerManager',
        events: 'EventBus',
        device: Any = None,  # DeviceManager - avoid circular import
        config: Any = None,  # ConfigManager
        services: Dict[str, Any] = None,
        device_manager: Any = None,  # Alias for device (backward compat)
    ):
        """
        Initialize the feature.

        Args:
            root: Tkinter root window
            state: Shared application state
            timers: Centralized timer manager
            events: Event bus for pub/sub
            device: Device connection manager
            config: Configuration manager
            services: Dictionary of available services
            device_manager: Alias for device (backward compatibility)
        """
        self.root = root
        self.state = state
        self.timers = timers
        self.events = events
        self.device = device or device_manager
        self.config = config
        self.services = services or {}

        # UI references (set in create_tab)
        self.tab_frame: Optional[ttk.Frame] = None
        self.send_button: Optional[ttk.Button] = None

        # Subscribe to connection events
        self.events.subscribe('connection_changed', self._on_connection_changed)

    @property
    def tab_title(self) -> str:
        """Get the tab title with optional icon."""
        if self.tab_icon:
            return f"{self.tab_icon} {self.display_name}"
        return self.display_name

    @abstractmethod
    def create_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """
        Create and return the tab UI for this feature.

        Args:
            notebook: Parent notebook widget

        Returns:
            The created tab frame
        """
        pass

    @abstractmethod
    def send_to_display(self) -> bool:
        """
        Send current feature content to the display.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop any running timers, animations, or background tasks."""
        pass

    @abstractmethod
    def create_preset(self, name: str) -> Dict[str, Any]:
        """
        Create a preset dictionary from current UI state.

        Args:
            name: Name for the preset

        Returns:
            Preset dictionary with all settings
        """
        pass

    @abstractmethod
    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """
        Execute a saved preset.

        Args:
            preset: Preset dictionary

        Returns:
            True if successful, False otherwise
        """
        pass

    def get_preset_preview(self, preset: Dict[str, Any]) -> str:
        """
        Get a short preview string for a preset.

        Override in subclasses for custom preview.

        Args:
            preset: Preset dictionary

        Returns:
            Short preview string
        """
        return preset.get('name', 'Unknown')

    def get_preset_details(self, preset: Dict[str, Any]) -> str:
        """
        Get detailed description for a preset.

        Override in subclasses for custom details.

        Args:
            preset: Preset dictionary

        Returns:
            Detailed description string
        """
        return f"Type: {self.display_name}"

    def _on_connection_changed(self, connected: bool) -> None:
        """
        Handle connection state changes.

        Enables/disables send button based on connection.
        """
        if self.send_button:
            if connected:
                self.send_button.state(['!disabled'])
            else:
                self.send_button.state(['disabled'])

    def require_connection(self) -> bool:
        """
        Check if device is connected, show warning if not.

        Returns:
            True if connected, False otherwise
        """
        if not self.state.is_connected:
            messagebox.showwarning(
                "Not Connected",
                "Please connect to a device first.",
                parent=self.root
            )
            return False
        return True

    def stop_other_features(self) -> None:
        """
        Stop all display-related timers before sending new content.

        This prevents old timers from interfering with new content.
        """
        self.timers.cancel_display_timers()
        self.state.reset_display_state()

    def set_active(self) -> None:
        """Mark this feature as the active display feature."""
        self.state.active_feature = self.feature_id
        self.events.publish('feature_activated', self.feature_id)

    def save_as_last_preset(self, preset: Dict[str, Any]) -> None:
        """
        Save preset reference for state restoration.

        Args:
            preset: Preset that was just executed
        """
        self.state.settings['last_preset'] = preset.get('name')

    def _create_send_button(
        self,
        parent: tk.Widget,
        text: str = "Send to Display",
        command: Optional[callable] = None
    ) -> ttk.Button:
        """
        Create a send button with proper connection state handling.

        Args:
            parent: Parent widget
            text: Button text
            command: Command to execute (defaults to send_to_display)

        Returns:
            The created button
        """
        self.send_button = ttk.Button(
            parent,
            text=text,
            command=command or self.send_to_display
        )

        # Set initial state based on connection
        if not self.state.is_connected:
            self.send_button.state(['disabled'])

        return self.send_button

    def _create_info_label(
        self,
        parent: tk.Widget,
        text: str,
        **kwargs
    ) -> ttk.Label:
        """
        Create an info label with consistent styling.

        Args:
            parent: Parent widget
            text: Label text
            **kwargs: Additional label options

        Returns:
            The created label
        """
        label = ttk.Label(
            parent,
            text=text,
            font=('TkDefaultFont', 9),
            foreground='gray',
            **kwargs
        )
        return label


class SimpleFeature(FeatureBase):
    """
    Simplified base class for features that don't need all callbacks.

    Provides default implementations for abstract methods.
    """

    def stop(self) -> None:
        """Default stop - cancel timers with feature prefix."""
        self.timers.cancel_by_prefix(f"{self.feature_id}_")

    def create_preset(self, name: str) -> Dict[str, Any]:
        """Default preset creation."""
        return {
            'name': name,
            'type': self.feature_id,
        }

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Default preset execution - just send to display."""
        return self.send_to_display()
