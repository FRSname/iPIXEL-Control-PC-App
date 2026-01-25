"""
Connection panel for device management.

Handles Bluetooth device scanning, connection, and status display.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, Callable


class ConnectionPanel(ttk.LabelFrame):
    """
    Connection panel widget.

    Provides UI for:
    - Scanning for Bluetooth LE devices
    - Connecting/disconnecting from devices
    - Displaying connection status
    """

    def __init__(
        self,
        parent,
        device_manager,
        state,
        on_connected: Optional[Callable] = None,
        on_disconnected: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, text="Connection", padding="10", **kwargs)

        self.device_manager = device_manager
        self.state = state
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected

        self.devices_dict: Dict[str, str] = {}

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the connection UI."""
        self.columnconfigure(1, weight=1)

        # Device selection row
        ttk.Label(self, text="Device:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            self,
            textvariable=self.device_var,
            state="readonly"
        )
        self.device_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))

        self.scan_btn = ttk.Button(
            self,
            text="Scan",
            command=self._scan_devices
        )
        self.scan_btn.grid(row=0, column=2, padx=(0, 5))

        self.connect_btn = ttk.Button(
            self,
            text="Connect",
            command=self._toggle_connection
        )
        self.connect_btn.grid(row=0, column=3)

        # Status row
        self.status_var = tk.StringVar(value="Not connected")
        self.status_label = ttk.Label(
            self,
            textvariable=self.status_var,
            foreground="red"
        )
        self.status_label.grid(row=1, column=0, columnspan=4, pady=(5, 0))

    def _scan_devices(self) -> None:
        """Scan for Bluetooth LE devices."""
        self.scan_btn.config(state=tk.DISABLED, text="Scanning...")
        self.device_combo['values'] = []

        self.device_manager.scan_devices(
            on_complete=self._on_scan_complete,
            on_error=self._on_scan_error
        )

    def _on_scan_complete(self, devices: Dict[str, str]) -> None:
        """Handle scan completion."""
        self.scan_btn.config(state=tk.NORMAL, text="Scan")

        if devices:
            self.devices_dict = devices
            self.device_combo['values'] = list(devices.keys())
            self.device_combo.current(0)
        else:
            self.status_var.set("No devices found")

    def _on_scan_error(self, error: str) -> None:
        """Handle scan error."""
        self.scan_btn.config(state=tk.NORMAL, text="Scan")
        messagebox.showerror("Scan Error", f"Failed to scan: {error}")

    def _toggle_connection(self) -> None:
        """Connect or disconnect from device."""
        if self.state.is_connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        """Connect to the selected device."""
        device_str = self.device_var.get()
        if not device_str:
            messagebox.showwarning("No Device", "Please scan and select a device first")
            return

        address = self.devices_dict.get(device_str)
        if not address:
            messagebox.showerror("Error", "Device address not found")
            return

        self.connect_btn.config(state=tk.DISABLED, text="Connecting...")

        self.device_manager.connect(
            address,
            on_success=self._on_connected,
            on_error=self._on_connection_error
        )

    def _on_connected(self) -> None:
        """Handle successful connection."""
        # Get device info and update state
        device_info = self.device_manager.get_device_info()
        if device_info:
            self.state.set_connected(device_info)
        else:
            # Create minimal device info if not available
            from ..core.state import DeviceInfo
            address = self.devices_dict.get(self.device_var.get(), "")
            self.state.set_connected(DeviceInfo(address=address))

        # Update UI
        device_info_text = "Connected"
        if device_info:
            device_info_text = f"Connected - {device_info.width}x{device_info.height}px"

        self.status_var.set(device_info_text)
        self.status_label.config(foreground="green")
        self.connect_btn.config(state=tk.NORMAL, text="Disconnect")

        if self.on_connected:
            self.on_connected()

    def _on_connection_error(self, error: str) -> None:
        """Handle connection error."""
        self.connect_btn.config(state=tk.NORMAL, text="Connect")
        messagebox.showerror("Connection Error", f"Failed to connect: {error}")

    def _disconnect(self) -> None:
        """Disconnect from the device."""
        self.device_manager.disconnect()

        self.state.set_disconnected()

        self.status_var.set("Disconnected")
        self.status_label.config(foreground="red")
        self.connect_btn.config(text="Connect")

        if self.on_disconnected:
            self.on_disconnected()

    def auto_connect(self, address: str) -> None:
        """Attempt to auto-connect to a known device."""
        self.devices_dict["Last Device"] = address
        self.device_combo['values'] = ["Last Device"]
        self.device_combo.current(0)
        self._connect()
