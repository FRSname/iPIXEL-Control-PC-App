"""
Main application orchestrator.

This is the new modular entry point that replaces the monolithic
ipixel_controller.py. It wires together all components and manages
the application lifecycle.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from .core import (
    AppState,
    TimerManager,
    EventBus,
    Events,
    ConfigManager,
    DeviceManager,
)
from .services import SpriteFontService
from .features import ALL_FEATURES, FeatureBase
from .ui import ConnectionPanel, ControlBoard, SettingsPanel


class iPixelApp:
    """
    Main application class.

    Orchestrates all components and manages the application lifecycle.
    This is the modern replacement for the monolithic iPixelController.

    Usage:
        app = iPixelApp()
        app.run()
    """

    def __init__(self):
        """Initialize the application."""
        # Create root window
        self.root = tk.Tk()
        self.root.title("iPixel LED Panel Controller")
        self.root.geometry("800x1000")
        self.root.minsize(700, 800)

        # Initialize core components
        self.events = EventBus()
        self.state = AppState()
        self.timers = TimerManager(self.root)
        self.config = ConfigManager(self.events)

        # Load configuration
        self.config.load_settings()
        self.config.load_presets()
        self.config.load_secrets()

        # Copy config to state for compatibility
        self.state.settings = self.config.settings
        self.state.presets = self.config.presets
        self.state.secrets = self.config.secrets
        self.state.sprite_fonts = self.config.get_sprite_fonts()

        # Initialize device manager
        self.device = DeviceManager(self.root, self.state, self.events)

        # Initialize services
        self.services: Dict[str, Any] = {}
        self.sprite_service = SpriteFontService()
        self.services['sprite_font'] = self.sprite_service
        self._init_sprite_fonts()

        # Features will be registered here
        self.features: Dict[str, FeatureBase] = {}

        # Setup UI
        self._setup_ui()

        # Register all features
        self._register_features()

        # Setup cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-connect if enabled
        if self.config.get_setting('auto_connect', True):
            last_device = self.config.get_setting('last_device')
            if last_device:
                self.root.after(1000, lambda: self._auto_connect(last_device))

    def _init_sprite_fonts(self):
        """Initialize sprite fonts from settings."""
        fonts = self.config.get_sprite_fonts()
        if fonts:
            self.sprite_service.register_fonts_from_settings(fonts)

    def _setup_ui(self):
        """Create the main user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Connection panel
        self.connection_panel = ConnectionPanel(
            main_frame,
            device_manager=self.device,
            state=self.state,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected
        )
        self.connection_panel.grid(
            row=0, column=0, columnspan=2,
            sticky=(tk.W, tk.E), pady=(0, 10)
        )

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(
            row=1, column=0, columnspan=2,
            sticky=(tk.W, tk.E, tk.N, tk.S),
            pady=(0, 10), padx=10
        )
        main_frame.rowconfigure(1, weight=1)

        # Control board tab (presets and playlists)
        self.control_board = ControlBoard(
            self.notebook,
            config=self.config,
            state=self.state,
            timers=self.timers,
            on_execute_preset=self._execute_preset
        )
        self.notebook.add(self.control_board, text="Control Board")

    def _register_features(self):
        """Register all feature plugins."""
        for feature_class in ALL_FEATURES:
            try:
                feature = feature_class(
                    root=self.root,
                    state=self.state,
                    config=self.config,
                    device=self.device,
                    timers=self.timers,
                    events=self.events,
                    services=self.services
                )

                # Create the feature's tab
                feature.create_tab(self.notebook)

                # Store reference
                self.features[feature.feature_id] = feature

            except Exception as e:
                print(f"Failed to register feature {feature_class.__name__}: {e}")

        # Settings tab at the end
        self.settings_panel = SettingsPanel(
            self.notebook,
            config=self.config,
            device_manager=self.device,
            state=self.state,
            on_sprite_fonts_changed=self._on_sprite_fonts_changed
        )
        self.notebook.add(self.settings_panel, text="Settings")

    def _on_connected(self):
        """Handle device connected event."""
        # Enable features
        for feature in self.features.values():
            if hasattr(feature, 'on_connected'):
                feature.on_connected()

        # Enable settings panel
        self.settings_panel.on_connected()

        # Restore last state if enabled
        if self.config.get_setting('restore_last_state', True):
            self.root.after(1000, self._restore_last_state)

    def _on_disconnected(self):
        """Handle device disconnected event."""
        # Stop all features
        for feature in self.features.values():
            feature.stop()
            if hasattr(feature, 'on_disconnected'):
                feature.on_disconnected()

        # Disable settings panel
        self.settings_panel.on_disconnected()

    def _on_sprite_fonts_changed(self):
        """Handle sprite fonts changed event."""
        # Reload fonts
        fonts = self.config.get_sprite_fonts()
        self.sprite_service.register_fonts_from_settings(fonts)
        self.state.sprite_fonts = fonts

        # Notify features
        for feature in self.features.values():
            if hasattr(feature, 'refresh_sprite_fonts'):
                feature.refresh_sprite_fonts()

    def _execute_preset(self, preset: Dict[str, Any]) -> bool:
        """Execute a preset through the appropriate feature."""
        preset_type = preset.get('type')

        if preset_type in self.features:
            feature = self.features[preset_type]
            try:
                return feature.execute_preset(preset)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to execute preset: {e}")
                return False
        else:
            messagebox.showwarning(
                "Unknown Preset",
                f"No feature found for preset type: {preset_type}"
            )
            return False

    def _auto_connect(self, address: str):
        """Attempt to auto-connect to a known device."""
        self.connection_panel.auto_connect(address)

    def _restore_last_state(self):
        """Restore the last used preset."""
        last_preset = self.config.get_setting('last_preset')
        if last_preset and isinstance(last_preset, dict):
            self._execute_preset(last_preset)

    def _on_close(self):
        """Handle window close."""
        # Stop all features
        for feature in self.features.values():
            feature.stop()

        # Cancel all timers
        self.timers.cancel_all()

        # Disconnect device
        if self.state.is_connected:
            self.device.disconnect()

        # Destroy window
        self.root.destroy()

    def run(self):
        """Run the application main loop."""
        self.root.mainloop()


def main():
    """Application entry point."""
    app = iPixelApp()
    app.run()


if __name__ == "__main__":
    main()
