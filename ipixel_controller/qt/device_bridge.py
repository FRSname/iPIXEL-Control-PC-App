"""Qt-friendly wrapper around the BLE device client.

The legacy ``ipixel_controller.core.device.DeviceManager`` is bound to
Tkinter (uses ``root.after`` to marshal callbacks). This module provides
the same operations using Qt signals + a background asyncio thread, so
the Qt UI never has to import Tkinter.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class DeviceInfo:
    address: str
    name: Optional[str] = None
    width: int = 64
    height: int = 16


class DeviceBridge(QObject):
    """Qt signal-based BLE bridge.

    Signals:
        scan_started: emitted before a scan begins
        scan_finished: emitted with {display_name: address} when done
        scan_failed: emitted with error message
        connecting: emitted when a connect attempt starts
        connected: emitted with DeviceInfo on success
        disconnected: emitted on disconnect / failure
        connection_failed: emitted with error message
        operation_failed: emitted with error message for runtime calls
    """

    scan_started = Signal()
    scan_finished = Signal(dict)
    scan_failed = Signal(str)

    connecting = Signal()
    connected = Signal(object)        # DeviceInfo
    disconnected = Signal()
    connection_failed = Signal(str)

    operation_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._client = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._devices: Dict[str, str] = {}
        self._device_info: Optional[DeviceInfo] = None
        self._start_loop()

    # ------------------------------------------------------------------ infra
    def _start_loop(self) -> None:
        ready = threading.Event()

        def run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            ready.set()
            self._loop.run_forever()

        threading.Thread(target=run, daemon=True, name="DeviceLoop").start()
        ready.wait(timeout=2.0)

    def _run_async(self, coro) -> Any:
        if not self._loop:
            return None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=30)

    def _spawn(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=fn, daemon=True).start()

    # ------------------------------------------------------------------ state
    @property
    def is_connected(self) -> bool:
        return self._device_info is not None

    @property
    def device_info(self) -> Optional[DeviceInfo]:
        return self._device_info

    @property
    def client(self):
        return self._client

    # ------------------------------------------------------------------ scan
    def scan(self, timeout: float = 5.0) -> None:
        self.scan_started.emit()

        def task() -> None:
            try:
                from bleak import BleakScanner

                async def discover():
                    return await BleakScanner.discover(timeout=timeout)

                devices = self._run_async(discover())
                results: Dict[str, str] = {}
                for d in devices or []:
                    name = getattr(d, "name", None) or ""
                    if name and any(k in name for k in ("LED", "BLE", "iPixel")):
                        results[f"{name} ({d.address})"] = d.address
                self._devices = results
                self.scan_finished.emit(results)
            except Exception as e:  # noqa: BLE001
                self.scan_failed.emit(str(e))

        self._spawn(task)

    @property
    def discovered(self) -> Dict[str, str]:
        return self._devices

    # --------------------------------------------------------------- connect
    def connect(self, address: str) -> None:
        self.connecting.emit()

        def task() -> None:
            try:
                from pypixelcolor import Client

                client = Client(address)
                if hasattr(client, "connect"):
                    result = client.connect()
                    if asyncio.iscoroutine(result):
                        self._run_async(result)
                info = DeviceInfo(address=address)
                src = getattr(client, "device_info", None)
                if src is not None:
                    info.width = getattr(src, "width", info.width)
                    info.height = getattr(src, "height", info.height)
                self._client = client
                self._device_info = info
                self.connected.emit(info)
            except Exception as e:  # noqa: BLE001
                self._client = None
                self._device_info = None
                self.connection_failed.emit(str(e))

        self._spawn(task)

    def disconnect(self) -> None:
        if self._client is None:
            self.disconnected.emit()
            return

        client = self._client
        self._client = None
        self._device_info = None

        def task() -> None:
            try:
                if hasattr(client, "disconnect"):
                    result = client.disconnect()
                    if asyncio.iscoroutine(result):
                        self._run_async(result)
            except Exception:
                pass
            self.disconnected.emit()

        self._spawn(task)

    # --------------------------------------------------------------- actions
    def _call(self, fn: Callable[[], Any]) -> None:
        def task() -> None:
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    self._run_async(result)
            except Exception as e:  # noqa: BLE001
                self.operation_failed.emit(str(e))

        self._spawn(task)

    def send_text(self, text: str, **kwargs) -> None:
        if not self._client:
            self.operation_failed.emit("Not connected")
            return
        # pypixelcolor rejects hex strings prefixed with '#'.
        for key in ("color", "bg_color"):
            val = kwargs.get(key)
            if isinstance(val, str) and val.startswith("#"):
                kwargs[key] = val.lstrip("#")
        self._call(lambda: self._client.send_text(text, **kwargs))

    def send_image(self, path: str, **kwargs) -> None:
        if not self._client:
            self.operation_failed.emit("Not connected")
            return
        self._call(lambda: self._client.send_image(path, **kwargs))

    def set_brightness(self, value: int) -> None:
        if not self._client:
            self.operation_failed.emit("Not connected")
            return
        self._call(lambda: self._client.set_brightness(int(value)))

    def set_power(self, on: bool) -> None:
        if not self._client:
            self.operation_failed.emit("Not connected")
            return
        self._call(
            lambda: self._client.power_on() if on else self._client.power_off()
        )

    def set_clock_mode(self, style: int = 0) -> None:
        if not self._client:
            self.operation_failed.emit("Not connected")
            return
        self._call(lambda: self._client.set_clock_mode(style=style))
