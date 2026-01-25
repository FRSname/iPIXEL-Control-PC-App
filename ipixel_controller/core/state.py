"""
Central application state management.

AppState is the single source of truth for all shared application state.
Components should read from and update this state rather than maintaining
their own copies.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class ConnectionStatus(Enum):
    """Device connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


@dataclass
class DeviceInfo:
    """Information about the connected device."""
    address: str
    name: Optional[str] = None
    width: int = 64
    height: int = 16


@dataclass
class AppState:
    """
    Central application state - single source of truth.

    This dataclass holds all shared state that needs to be accessed
    by multiple components. It replaces the scattered instance variables
    in the original monolithic class.
    """

    # Connection state
    connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    device_info: Optional[DeviceInfo] = None

    # Active display state
    active_feature: Optional[str] = None  # "text", "clock", "stock", etc.

    # Feature-specific cached data
    current_stock_data: Optional[Dict[str, Any]] = None
    current_youtube_data: Optional[Dict[str, Any]] = None
    current_weather_data: Optional[Dict[str, Any]] = None

    # Configuration
    presets: List[Dict[str, Any]] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    secrets: Dict[str, Any] = field(default_factory=dict)
    sprite_fonts: List[Dict[str, Any]] = field(default_factory=list)

    # Playlist state
    playlist: List[Dict[str, Any]] = field(default_factory=list)
    playlist_running: bool = False
    playlist_paused: bool = False
    playlist_index: int = 0
    current_playlist_file: Optional[str] = None

    # Animation state
    animation_running: bool = False
    animation_state: Optional[Dict[str, Any]] = None

    # Clock state
    clock_running: bool = False

    # Sprite scroll state
    sprite_scroll_running: bool = False

    # Teams monitoring state
    teams_monitoring: bool = False
    teams_access_token: Optional[str] = None
    teams_refresh_token: Optional[str] = None
    teams_last_status: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self.connection_status == ConnectionStatus.CONNECTED

    @property
    def device_address(self) -> Optional[str]:
        """Get connected device address."""
        return self.device_info.address if self.device_info else None

    def reset_display_state(self) -> None:
        """Reset all active display states (called before new content)."""
        self.clock_running = False
        self.animation_running = False
        self.sprite_scroll_running = False
        self.animation_state = None

    def set_connected(self, device_info: DeviceInfo) -> None:
        """Set connection state to connected."""
        self.connection_status = ConnectionStatus.CONNECTED
        self.device_info = device_info

    def set_disconnected(self) -> None:
        """Set connection state to disconnected."""
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.device_info = None
        self.reset_display_state()
