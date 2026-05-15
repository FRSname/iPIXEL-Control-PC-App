"""Home page — preset grid and playlist controls.

This is the landing view. It surfaces user-saved presets (one click to
send to the panel) and the playlist controls so the panel can cycle
through presets unattended.

Playlists are stored in ``playlists/*.json`` with the legacy shape
``{"name", "items": [{"preset_name", "duration"}, ...]}`` and resolved
against the preset library on play.
"""

from __future__ import annotations

import json
import os
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..playlist import PlaylistPlayer, resolve_preset
from ..widgets import Card
from .base import Page


TYPE_ICONS: Dict[str, str] = {
    "text": "T",
    "image": "I",
    "clock": "C",
    "stock": "$",
    "youtube": "Y",
    "weather": "W",
    "animation": "A",
    "teams": "M",
}

PLAYLISTS_DIR = "playlists"


# =============================================================== preset tile

class _PresetTile(QWidget):
    """One preset row: clickable run-area + small delete button.

    The run-area takes ~all the width and triggers ``on_run(preset)``;
    the trailing × button triggers ``on_delete(preset)``.
    """

    def __init__(
        self,
        preset: dict,
        on_run: Callable[[dict], None],
        on_delete: Callable[[dict], None],
    ) -> None:
        super().__init__()
        name = preset.get("name", "Preset")[:24]
        ptype = preset.get("type", "?")
        icon = TYPE_ICONS.get(ptype, "•")

        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        run_btn = QPushButton(f"{icon}   {name}")
        run_btn.setMinimumHeight(64)
        run_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        run_btn.setCursor(Qt.PointingHandCursor)
        run_btn.clicked.connect(lambda: on_run(preset))
        row.addWidget(run_btn, 1)

        del_btn = QPushButton("×")
        del_btn.setFixedWidth(34)
        del_btn.setMinimumHeight(64)
        del_btn.setToolTip(f"Delete preset '{name}'")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda: on_delete(preset))
        row.addWidget(del_btn)


# ============================================================== editor dialog

class _PlaylistEditor(QDialog):
    """Reorder, add/remove, set duration on the current playlist's items."""

    def __init__(
        self,
        items: List[dict],
        presets: List[dict],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit playlist")
        self.resize(560, 460)
        self._items = list(items)
        self._presets = presets

        outer = QVBoxLayout(self)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SingleSelection)
        outer.addWidget(self._list, 1)

        # Item controls
        ctl = QHBoxLayout()

        up = QPushButton("↑")
        up.clicked.connect(self._move_up)
        ctl.addWidget(up)

        down = QPushButton("↓")
        down.clicked.connect(self._move_down)
        ctl.addWidget(down)

        rm = QPushButton("Remove")
        rm.clicked.connect(self._remove)
        ctl.addWidget(rm)

        ctl.addStretch()

        ctl.addWidget(QLabel("Duration"))
        self._duration = QDoubleSpinBox()
        self._duration.setRange(1.0, 600.0)
        self._duration.setDecimals(1)
        self._duration.setSingleStep(1.0)
        self._duration.setSuffix(" s")
        self._duration.setValue(10.0)
        self._duration.valueChanged.connect(self._update_duration)
        ctl.addWidget(self._duration)

        outer.addLayout(ctl)

        # Add row
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Add preset"))
        self._add_combo = QComboBox()
        self._add_combo.setMinimumWidth(220)
        for p in presets:
            self._add_combo.addItem(p.get("name", "?"))
        add_row.addWidget(self._add_combo, 1)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add)
        add_row.addWidget(add_btn)
        outer.addLayout(add_row)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        self._refresh()
        self._list.currentRowChanged.connect(self._on_select)

    # --------------------------------------------------------------- helpers
    def _refresh(self) -> None:
        self._list.clear()
        for i, item in enumerate(self._items):
            preset = resolve_preset(item, self._presets)
            name = (
                preset.get("name") if preset else item.get("preset_name", "<missing>")
            )
            dur = float(item.get("duration", 30))
            self._list.addItem(f"{i + 1}. {name}  —  {dur:g}s")

    def _on_select(self, row: int) -> None:
        if 0 <= row < len(self._items):
            self._duration.blockSignals(True)
            self._duration.setValue(float(self._items[row].get("duration", 10)))
            self._duration.blockSignals(False)

    def _update_duration(self, value: float) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._items):
            self._items[row]["duration"] = value
            self._refresh()
            self._list.setCurrentRow(row)

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row > 0:
            self._items[row - 1], self._items[row] = self._items[row], self._items[row - 1]
            self._refresh()
            self._list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._items) - 1:
            self._items[row + 1], self._items[row] = self._items[row], self._items[row + 1]
            self._refresh()
            self._list.setCurrentRow(row + 1)

    def _remove(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._items):
            del self._items[row]
            self._refresh()

    def _add(self) -> None:
        name = self._add_combo.currentText()
        if not name:
            return
        self._items.append({"preset_name": name, "duration": 10})
        self._refresh()
        self._list.setCurrentRow(len(self._items) - 1)

    def result_items(self) -> List[dict]:
        return self._items


# ===================================================================== page

class HomePage(Page):
    title = "Presets"
    subtitle = "Saved presets and playlists. Click a preset to send it to the panel."

    def __init__(
        self,
        config,
        on_run_preset: Callable[[dict], None],
        on_open_text: Callable[[], None],
    ) -> None:
        super().__init__()
        self._config = config
        self._on_run_preset = on_run_preset
        self._on_open_text = on_open_text

        self._player = PlaylistPlayer(self)
        self._player.status_changed.connect(self._set_playlist_status)
        self._configure_player()

        self._current_playlist_path: Optional[str] = None
        self._items: List[dict] = []

        # ----- Quick actions -----
        actions = Card(title="Quick actions")
        row = QHBoxLayout()
        row.setSpacing(8)

        new_text_btn = QPushButton("Send text")
        new_text_btn.setObjectName("PrimaryButton")
        new_text_btn.clicked.connect(lambda: on_open_text())
        row.addWidget(new_text_btn)

        refresh_btn = QPushButton("Refresh presets")
        refresh_btn.clicked.connect(self.refresh)
        row.addWidget(refresh_btn)
        row.addStretch()
        actions.add_layout(row)
        self.content_layout().addWidget(actions)

        # ----- Presets grid -----
        self._presets_card = Card(title="Saved presets")
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setMinimumHeight(220)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._grid_host)
        self._presets_card.add(self._scroll)
        self.content_layout().addWidget(self._presets_card)

        # ----- Playlist -----
        self._playlist_card = self._build_playlist_card()
        self.content_layout().addWidget(self._playlist_card)

        self.refresh()
        self._refresh_playlist_combo()

    # ============================================================== player
    def _configure_player(self) -> None:
        self._player.configure(
            self._config.get_presets(),
            # Playlist autoplay should not yank the user off whatever
            # menu page they're browsing — fire the preset in place.
            lambda preset: self._on_run_preset(preset, switch_page=False),
        )

    # ============================================================== preset
    def refresh(self) -> None:
        # Clear current grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        presets: List[dict] = self._config.get_presets()
        # Refresh the player's preset list too — presets may have been
        # added/removed since last load.
        self._configure_player()

        if not presets:
            empty = QLabel(
                "No presets yet. Open a feature, configure it, then click "
                "'Save as preset'."
            )
            empty.setWordWrap(True)
            empty.setStyleSheet("color:#6c7086; padding: 24px;")
            self._grid.addWidget(empty, 0, 0)
            return

        cols = 3
        for i, preset in enumerate(presets):
            tile = _PresetTile(preset, self._on_run_preset, self._delete_preset)
            self._grid.addWidget(tile, i // cols, i % cols)

    def _delete_preset(self, preset: dict) -> None:
        """Confirm + delete the given preset, then refresh the grid."""
        name = preset.get("name", "this preset")
        if (
            QMessageBox.question(
                self,
                "Delete preset",
                f"Delete preset '{name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        presets = self._config.get_presets()
        target_name = preset.get("name")
        target_type = preset.get("type")
        for i, p in enumerate(presets):
            if p is preset or (
                p.get("name") == target_name and p.get("type") == target_type
            ):
                self._config.delete_preset(i)
                break
        self.refresh()

    def on_shown(self) -> None:
        self.refresh()

    def on_connection_changed(self, connected: bool) -> None:
        # If we lose the device mid-playlist, stop firing presets at it.
        if not connected and self._player.is_running:
            self._player.stop()
            self._set_playlist_status("Stopped — device disconnected.")

    # ============================================================ playlist UI
    def _build_playlist_card(self) -> Card:
        card = Card(title="Playlist")

        # Selector row
        row = QHBoxLayout()
        row.addWidget(QLabel("Playlist"))
        self._playlist_combo = QComboBox()
        self._playlist_combo.setMinimumWidth(220)
        self._playlist_combo.currentIndexChanged.connect(self._on_playlist_pick)
        row.addWidget(self._playlist_combo, 1)

        reload_btn = QPushButton("↻")
        reload_btn.setToolTip("Rescan playlists folder")
        reload_btn.setMaximumWidth(36)
        reload_btn.clicked.connect(self._refresh_playlist_combo)
        row.addWidget(reload_btn)

        card.add_layout(row)

        # Transport
        transport = QHBoxLayout()
        play_btn = QPushButton("Play")
        play_btn.setObjectName("PrimaryButton")
        play_btn.clicked.connect(self._player.play)
        transport.addWidget(play_btn)

        pause_btn = QPushButton("Pause")
        pause_btn.clicked.connect(self._player.pause)
        transport.addWidget(pause_btn)

        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self._player.stop)
        transport.addWidget(stop_btn)

        edit_btn = QPushButton("Edit…")
        edit_btn.clicked.connect(self._edit_playlist)
        transport.addWidget(edit_btn)

        transport.addStretch()
        card.add_layout(transport)

        # Save/load
        manage = QHBoxLayout()
        save_btn = QPushButton("Save as…")
        save_btn.clicked.connect(self._save_playlist)
        manage.addWidget(save_btn)

        load_btn = QPushButton("Load file…")
        load_btn.clicked.connect(self._load_playlist_dialog)
        manage.addWidget(load_btn)

        new_btn = QPushButton("New playlist")
        new_btn.clicked.connect(self._new_playlist)
        manage.addWidget(new_btn)

        manage.addStretch()
        card.add_layout(manage)

        self._playlist_status = QLabel("No playlist loaded")
        self._playlist_status.setStyleSheet("color:#a6adc8;")
        card.add(self._playlist_status)

        return card

    def _set_playlist_status(self, text: str) -> None:
        self._playlist_status.setText(text)

    # ------------------------------------------------------------- playlists
    def _playlists_dir(self) -> str:
        path = os.path.join(os.getcwd(), PLAYLISTS_DIR)
        os.makedirs(path, exist_ok=True)
        return path

    def _refresh_playlist_combo(self) -> None:
        self._playlist_combo.blockSignals(True)
        self._playlist_combo.clear()
        self._playlist_combo.addItem("(Unsaved playlist)", "")
        try:
            for entry in sorted(os.listdir(self._playlists_dir())):
                if entry.lower().endswith(".json"):
                    full = os.path.join(self._playlists_dir(), entry)
                    self._playlist_combo.addItem(entry, full)
        except FileNotFoundError:
            pass
        self._playlist_combo.blockSignals(False)

    def _on_playlist_pick(self, _idx: int) -> None:
        path = self._playlist_combo.currentData()
        if not path:
            self._items = []
            self._current_playlist_path = None
            self._player.set_items(self._items)
            self._set_playlist_status("New playlist")
            return
        self._load_playlist_file(path)

    def _load_playlist_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(e))
            return
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            QMessageBox.critical(self, "Load failed", "Playlist file has no items list.")
            return
        self._items = items
        self._current_playlist_path = path
        self._player.set_items(self._items)
        self._set_playlist_status(
            f"Loaded {len(self._items)} items from {os.path.basename(path)}"
        )

    def _load_playlist_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load playlist",
            self._playlists_dir(),
            "Playlist JSON (*.json);;All files (*.*)",
        )
        if path:
            self._load_playlist_file(path)
            self._refresh_playlist_combo()
            # Select it in the combo so save-on-edit roundtrips correctly.
            idx = self._playlist_combo.findData(path)
            if idx >= 0:
                self._playlist_combo.setCurrentIndex(idx)

    def _save_playlist(self) -> None:
        if not self._items:
            QMessageBox.warning(self, "Empty", "Playlist is empty.")
            return
        default_dir = self._playlists_dir()
        default_path = self._current_playlist_path or os.path.join(default_dir, "playlist.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save playlist", default_path, "Playlist JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"name": os.path.basename(path), "items": self._items},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._current_playlist_path = path
        self._refresh_playlist_combo()
        idx = self._playlist_combo.findData(path)
        if idx >= 0:
            self._playlist_combo.setCurrentIndex(idx)
        QMessageBox.information(self, "Saved", "Playlist saved.")

    def _new_playlist(self) -> None:
        if self._items and QMessageBox.question(
            self, "Discard current?",
            "Replace the current playlist with an empty one?",
        ) != QMessageBox.Yes:
            return
        self._items = []
        self._current_playlist_path = None
        self._player.set_items(self._items)
        self._playlist_combo.setCurrentIndex(0)
        self._set_playlist_status("New playlist")

    def _edit_playlist(self) -> None:
        presets = self._config.get_presets()
        if not presets:
            QMessageBox.warning(self, "No presets", "Create some presets first.")
            return
        dlg = _PlaylistEditor(self._items, presets, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._items = dlg.result_items()
            self._player.set_items(self._items)
            self._set_playlist_status(f"{len(self._items)} items ready")
