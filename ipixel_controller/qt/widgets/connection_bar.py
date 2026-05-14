"""Top bar showing connection status and quick connect controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ..device_bridge import DeviceBridge, DeviceInfo


class ConnectionBar(QFrame):
    """A persistent strip across the top of the window.

    Houses: status indicator, device combo, Scan and Connect/Disconnect buttons.
    All BLE calls go through the injected :class:`DeviceBridge`; UI updates
    happen via the bridge's Qt signals.
    """

    connected = Signal(object)
    disconnected = Signal()

    def __init__(self, device: DeviceBridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConnectionBar")
        self.setFixedHeight(56)
        self._device = device

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(12)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setProperty("state", "disconnected")
        self.status_dot.setFixedWidth(14)
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("Disconnected")
        layout.addWidget(self.status_label)

        layout.addSpacing(12)

        self.device_combo = QComboBox()
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.device_combo.setMinimumWidth(280)
        self.device_combo.setPlaceholderText("No devices yet — click Scan")
        layout.addWidget(self.device_combo, 1)

        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self._on_scan)
        layout.addWidget(self.scan_btn)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("PrimaryButton")
        self.connect_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.connect_btn)

        # Wire signals from bridge
        device.scan_started.connect(self._on_scan_started)
        device.scan_finished.connect(self._on_scan_finished)
        device.scan_failed.connect(self._on_scan_failed)
        device.connecting.connect(self._on_connecting)
        device.connected.connect(self._on_connected)
        device.connection_failed.connect(self._on_connection_failed)
        device.disconnected.connect(self._on_disconnected)

    # --------------------------------------------------------------- scanning
    def _on_scan(self) -> None:
        self._device.scan()

    def _on_scan_started(self) -> None:
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning…")
        self.device_combo.clear()

    def _on_scan_finished(self, devices: dict) -> None:
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan")
        self.device_combo.clear()
        if not devices:
            self.device_combo.setPlaceholderText("No iPixel devices found")
            return
        for label, addr in devices.items():
            self.device_combo.addItem(label, addr)

    def _on_scan_failed(self, error: str) -> None:
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan")
        self._set_status("Scan failed", "disconnected")
        self.device_combo.setPlaceholderText(f"Scan failed: {error}")

    # ------------------------------------------------------------- connecting
    def _on_toggle(self) -> None:
        if self._device.is_connected:
            self._device.disconnect()
            return
        addr = self.device_combo.currentData()
        if not addr:
            self._set_status("Select a device first", "disconnected")
            return
        self._device.connect(addr)

    def _on_connecting(self) -> None:
        self._set_status("Connecting…", "connecting")
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting…")

    def _on_connected(self, info: DeviceInfo) -> None:
        self._set_status(f"Connected · {info.width}×{info.height}", "connected")
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setObjectName("")  # secondary style when connected
        self._restyle(self.connect_btn)
        self.connected.emit(info)

    def _on_connection_failed(self, error: str) -> None:
        self._set_status(f"Failed: {error}", "disconnected")
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.connect_btn.setObjectName("PrimaryButton")
        self._restyle(self.connect_btn)

    def _on_disconnected(self) -> None:
        self._set_status("Disconnected", "disconnected")
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.connect_btn.setObjectName("PrimaryButton")
        self._restyle(self.connect_btn)
        self.disconnected.emit()

    # ---------------------------------------------------------------- helpers
    def _set_status(self, text: str, state: str) -> None:
        self.status_label.setText(text)
        self.status_dot.setProperty("state", state)
        # Force re-evaluation of dynamic property in QSS
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)

    @staticmethod
    def _restyle(w) -> None:
        w.style().unpolish(w)
        w.style().polish(w)
