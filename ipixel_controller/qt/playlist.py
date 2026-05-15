"""Playlist engine — cycles presets through a callable on a timer.

Playlist files live in the ``playlists/`` folder and have the legacy
shape::

    {"name": "...", "items": [{"preset_name": "...", "duration": 10}, ...]}

Items can also embed the preset directly under ``preset`` (in-memory
case) — :func:`resolve_preset` handles both. Durations are seconds.

The engine is UI-agnostic; the home page wires it to Play/Pause/Stop
buttons and a status label.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal


def resolve_preset(item: Dict[str, Any], presets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the preset dict referenced by a playlist item, or None."""
    embedded = item.get("preset")
    if isinstance(embedded, dict):
        return embedded
    name = item.get("preset_name")
    if isinstance(name, str):
        for p in presets:
            if p.get("name") == name:
                return p
    return None


class PlaylistPlayer(QObject):
    """Cycles a list of playlist items through ``run(preset)`` callbacks."""

    status_changed = Signal(str)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.items: List[Dict[str, Any]] = []
        self._index = 0
        self._paused = False
        self._running = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        self._presets: List[Dict[str, Any]] = []
        self._run_preset: Optional[Callable[[Dict[str, Any]], None]] = None

    # --------------------------------------------------------------- config
    def configure(
        self,
        presets: List[Dict[str, Any]],
        run_preset: Callable[[Dict[str, Any]], None],
    ) -> None:
        self._presets = presets
        self._run_preset = run_preset

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self.items = list(items)
        self.stop()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_index(self) -> int:
        return self._index

    # ---------------------------------------------------------------- control
    def play(self) -> None:
        if not self.items:
            self.status_changed.emit("Playlist is empty")
            return
        if self._paused:
            self._paused = False
            self.status_changed.emit(self._status_text())
            self._fire_current()
            return
        self._running = True
        self._paused = False
        self._index = 0
        self._fire_current()

    def pause(self) -> None:
        if not self._running:
            return
        self._paused = True
        self._timer.stop()
        self.status_changed.emit("Paused")

    def stop(self) -> None:
        self._running = False
        self._paused = False
        self._index = 0
        self._timer.stop()
        self.status_changed.emit("Stopped")

    # ---------------------------------------------------------------- engine
    def _fire_current(self) -> None:
        if not self._running or self._paused:
            return
        if not self.items:
            self.stop()
            self.finished.emit()
            return
        if self._index >= len(self.items):
            # Loop forever, matching legacy behaviour.
            self._index = 0

        item = self.items[self._index]
        preset = resolve_preset(item, self._presets)
        name = (
            preset.get("name") if preset else item.get("preset_name", "<missing>")
        )
        self.status_changed.emit(
            f"Playing {self._index + 1}/{len(self.items)} — {name}"
        )

        if preset is not None and self._run_preset is not None:
            try:
                self._run_preset(preset)
            except Exception as e:  # noqa: BLE001
                self.status_changed.emit(f"Preset failed: {e}")

        duration_s = float(item.get("duration", 30))
        self._timer.start(max(1, int(duration_s * 1000)))

    def _advance(self) -> None:
        if not self._running or self._paused:
            return
        self._index += 1
        self._fire_current()

    def _status_text(self) -> str:
        if not self.items:
            return "Empty"
        if self._paused:
            return "Paused"
        if self._running:
            return f"Playing {self._index + 1}/{len(self.items)}"
        return "Stopped"
