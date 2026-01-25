"""
Device manager for BLE communication.

Handles Bluetooth device scanning, connection, and communication with
the LED panel. Manages the async event loop bridge for Tkinter integration.
"""

import asyncio
import threading
from typing import Optional, Dict, Callable, Any
import tkinter as tk

from .state import AppState, ConnectionStatus, DeviceInfo
from .events import EventBus, Events


class DeviceManager:
    """
    Manages BLE device connection and communication.

    Handles the Tkinter <-> asyncio threading bridge required for
    Bluetooth Low Energy operations.

    Features:
    - Device scanning with filtering
    - Async connection management
    - Thread-safe communication
    - Event publishing for state changes
    """

    def __init__(
        self,
        root: tk.Tk,
        state: AppState,
        events: EventBus
    ):
        """
        Initialize the device manager.

        Args:
            root: Tkinter root window for thread-safe callbacks
            state: Shared application state
            events: Event bus for publishing connection events
        """
        self._root = root
        self._state = state
        self._events = events

        self._client = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._devices: Dict[str, str] = {}  # display_name -> address

        # Start async event loop in separate thread
        self._start_event_loop()

    def _start_event_loop(self) -> None:
        """Start asyncio event loop in a background thread."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

    def run_async(self, coro) -> Any:
        """
        Run an async coroutine in the event loop.

        Thread-safe method to execute async operations from the main thread.

        Args:
            coro: Async coroutine to execute

        Returns:
            Result of the coroutine
        """
        if self._loop:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=30)
        return None

    def scan_devices(
        self,
        on_complete: Callable[[Dict[str, str]], None],
        on_error: Callable[[str], None],
        timeout: float = 5.0
    ) -> None:
        """
        Scan for BLE devices in a background thread.

        Args:
            on_complete: Callback with dict of {display_name: address}
            on_error: Callback for errors
            timeout: Scan timeout in seconds
        """
        self._events.publish(Events.DEVICE_SCANNING, True)

        def scan_task():
            try:
                from bleak import BleakScanner

                async def do_scan():
                    devices = await BleakScanner.discover(timeout=timeout)
                    return devices

                devices = self.run_async(do_scan())

                # Filter for iPixel devices
                ipixel_devices = {}
                for device in devices:
                    if device.name and any(k in device.name for k in ("LED", "BLE", "iPixel")):
                        display_name = f"{device.name} ({device.address})"
                        ipixel_devices[display_name] = device.address

                self._devices = ipixel_devices
                self._root.after(0, lambda: on_complete(ipixel_devices))

            except Exception as e:
                error_msg = str(e)
                self._root.after(0, lambda err=error_msg: on_error(err))
            finally:
                self._root.after(0, lambda: self._events.publish(Events.DEVICE_SCAN_COMPLETE, True))

        threading.Thread(target=scan_task, daemon=True).start()

    def connect(
        self,
        address: str,
        on_success: Callable[[], None],
        on_error: Callable[[str], None]
    ) -> None:
        """
        Connect to a BLE device.

        Args:
            address: Device Bluetooth address
            on_success: Callback on successful connection
            on_error: Callback on connection error
        """
        self._state.connection_status = ConnectionStatus.CONNECTING

        def connect_task():
            try:
                from pypixelcolor import Client

                self._client = Client(address)

                # Try to connect if method exists
                if hasattr(self._client, 'connect') and callable(self._client.connect):
                    result = self._client.connect()
                    if asyncio.iscoroutine(result):
                        self.run_async(result)

                # Get device info
                device_info = DeviceInfo(address=address)
                if hasattr(self._client, 'device_info') and self._client.device_info:
                    info = self._client.device_info
                    if hasattr(info, 'width'):
                        device_info.width = info.width
                    if hasattr(info, 'height'):
                        device_info.height = info.height

                self._state.set_connected(device_info)
                self._root.after(0, lambda: self._on_connected(on_success))

            except Exception as e:
                self._state.connection_status = ConnectionStatus.DISCONNECTED
                error_msg = str(e)
                self._root.after(0, lambda err=error_msg: on_error(err))

        threading.Thread(target=connect_task, daemon=True).start()

    def _on_connected(self, callback: Callable[[], None]) -> None:
        """Handle successful connection."""
        self._events.publish(Events.CONNECTION_CHANGED, True)
        callback()

    def disconnect(self) -> None:
        """Disconnect from the current device."""
        if self._client:
            try:
                if hasattr(self._client, 'disconnect'):
                    result = self._client.disconnect()
                    if asyncio.iscoroutine(result):
                        self.run_async(result)
            except Exception:
                pass

        self._client = None
        self._state.set_disconnected()
        self._events.publish(Events.CONNECTION_CHANGED, False)

    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._state.is_connected

    @property
    def client(self):
        """Get the pypixelcolor client."""
        return self._client

    def get_device_info(self):
        """Get device info from state."""
        return self._state.device_info

    @property
    def devices(self) -> Dict[str, str]:
        """Get discovered devices."""
        return self._devices

    # Convenience methods for common operations

    def send_text(
        self,
        text: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> None:
        """
        Send text to the display.

        Args:
            text: Text to display
            on_complete: Optional success callback
            on_error: Optional error callback
            **kwargs: Additional arguments for send_text
        """
        if not self._client:
            if on_error:
                on_error("Not connected")
            return

        def task():
            try:
                result = self._client.send_text(text, **kwargs)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
                if on_complete:
                    self._root.after(0, on_complete)
            except Exception as e:
                if on_error:
                    error_msg = str(e)
                    self._root.after(0, lambda err=error_msg: on_error(err))

        threading.Thread(target=task, daemon=True).start()

    def send_image(
        self,
        path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> None:
        """
        Send an image to the display.

        Args:
            path: Path to image file
            on_complete: Optional success callback
            on_error: Optional error callback
            **kwargs: Additional arguments for send_image
        """
        if not self._client:
            if on_error:
                on_error("Not connected")
            return

        def task():
            try:
                result = self._client.send_image(path, **kwargs)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
                if on_complete:
                    self._root.after(0, on_complete)
            except Exception as e:
                if on_error:
                    error_msg = str(e)
                    self._root.after(0, lambda err=error_msg: on_error(err))

        threading.Thread(target=task, daemon=True).start()

    def set_brightness(
        self,
        value: int,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        Set display brightness.

        Args:
            value: Brightness value (1-100)
            on_complete: Optional success callback
            on_error: Optional error callback
        """
        if not self._client:
            if on_error:
                on_error("Not connected")
            return

        def task():
            try:
                result = self._client.set_brightness(value)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
                if on_complete:
                    self._root.after(0, on_complete)
            except Exception as e:
                if on_error:
                    error_msg = str(e)
                    self._root.after(0, lambda err=error_msg: on_error(err))

        threading.Thread(target=task, daemon=True).start()

    def set_power(
        self,
        on: bool,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        Set display power state.

        Args:
            on: True for on, False for off
            on_complete: Optional success callback
            on_error: Optional error callback
        """
        if not self._client:
            if on_error:
                on_error("Not connected")
            return

        def task():
            try:
                if on:
                    result = self._client.power_on()
                else:
                    result = self._client.power_off()
                if asyncio.iscoroutine(result):
                    self.run_async(result)
                if on_complete:
                    self._root.after(0, on_complete)
            except Exception as e:
                if on_error:
                    error_msg = str(e)
                    self._root.after(0, lambda err=error_msg: on_error(err))

        threading.Thread(target=task, daemon=True).start()

    def set_clock_mode(self, style: int = 0) -> None:
        """
        Set display to clock mode.

        Args:
            style: Clock style (0-8)
        """
        if not self._client:
            return

        def task():
            try:
                result = self._client.set_clock_mode(style=style)
                if asyncio.iscoroutine(result):
                    self.run_async(result)
            except Exception:
                pass

        threading.Thread(target=task, daemon=True).start()
