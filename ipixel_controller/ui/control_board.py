"""
Control board for preset and playlist management.

Provides quick access to saved presets and playlist functionality.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, List, Optional, Callable
import json
import os
from PIL import Image, ImageTk
import base64
import io


class ControlBoard(ttk.Frame):
    """
    Control board widget.

    Provides UI for:
    - Displaying and executing saved presets
    - Managing playlists
    - Import/export presets
    """

    def __init__(
        self,
        parent,
        config,
        state,
        timers,
        on_execute_preset: Optional[Callable[[Dict[str, Any]], bool]] = None,
        **kwargs
    ):
        super().__init__(parent, padding="10", **kwargs)

        self.config = config
        self.state = state
        self.timers = timers
        self.on_execute_preset = on_execute_preset

        # Playlist state
        self.playlist: List[Dict[str, Any]] = []
        self.playlist_running = False
        self.playlist_paused = False
        self.playlist_index = 0
        self.current_playlist_file: Optional[str] = None

        # Thumbnail cache for preset previews
        self.thumbnail_cache: Dict[str, ImageTk.PhotoImage] = {}

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the control board UI."""
        self.columnconfigure(0, weight=1)

        # Info label
        info_label = ttk.Label(
            self,
            text="Quick access to saved presets. Create presets in other tabs and save them here.",
            font=('TkDefaultFont', 9, 'italic'),
            wraplength=750
        )
        info_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Presets area
        presets_frame = ttk.LabelFrame(self, text="Saved Presets", padding="10")
        presets_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.rowconfigure(1, weight=1)

        # Scrollable preset container
        canvas_frame = ttk.Frame(presets_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.presets_canvas = tk.Canvas(canvas_frame, height=400)
        scrollbar = ttk.Scrollbar(
            canvas_frame,
            orient="vertical",
            command=self.presets_canvas.yview
        )
        self.presets_scrollable_frame = ttk.Frame(self.presets_canvas)

        self.presets_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.presets_canvas.configure(
                scrollregion=self.presets_canvas.bbox("all")
            )
        )

        self.presets_canvas.create_window(
            (0, 0),
            window=self.presets_scrollable_frame,
            anchor="nw"
        )
        self.presets_canvas.configure(yscrollcommand=scrollbar.set)

        self.presets_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        self._bind_mousewheel()

        # Playlist section
        playlist_frame = ttk.LabelFrame(
            self,
            text="Playlist - Auto Switch Presets",
            padding="10"
        )
        playlist_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 10))

        # Playlist controls
        playlist_control_frame = ttk.Frame(playlist_frame)
        playlist_control_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(
            playlist_control_frame,
            text="Play",
            command=self.play_playlist,
            width=10
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            playlist_control_frame,
            text="Pause",
            command=self.pause_playlist,
            width=10
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            playlist_control_frame,
            text="Stop",
            command=self.stop_playlist,
            width=10
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            playlist_control_frame,
            text="Edit Playlist",
            command=self.edit_playlist,
            width=15
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Playlist management buttons
        playlist_manage_frame = ttk.Frame(playlist_frame)
        playlist_manage_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(
            playlist_manage_frame,
            text="Save Playlist As...",
            command=self.save_playlist,
            width=18
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            playlist_manage_frame,
            text="Load Playlist",
            command=self.load_playlist_dialog,
            width=18
        ).pack(side=tk.LEFT, padx=(0, 5))

        # Current playlist name
        self.current_playlist_name_var = tk.StringVar(value="(Unsaved playlist)")
        ttk.Label(
            playlist_manage_frame,
            textvariable=self.current_playlist_name_var,
            font=('TkDefaultFont', 8, 'italic'),
            foreground='gray'
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Playlist status
        self.playlist_status_var = tk.StringVar(value="Playlist: Not running")
        ttk.Label(
            playlist_control_frame,
            textvariable=self.playlist_status_var,
            font=('TkDefaultFont', 9, 'italic')
        ).pack(side=tk.LEFT, padx=(20, 0))

        # Action buttons
        action_frame = ttk.Frame(self)
        action_frame.grid(row=3, column=0, pady=(10, 0))

        ttk.Button(
            action_frame,
            text="Import Presets",
            command=self.import_presets
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            action_frame,
            text="Export Presets",
            command=self.export_presets
        ).pack(side=tk.LEFT)

        # Initial render
        self.refresh_preset_buttons()

    def _bind_mousewheel(self) -> None:
        """Bind mouse wheel scrolling."""
        def on_mousewheel(event):
            if event.num == 4:
                self.presets_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.presets_canvas.yview_scroll(1, "units")
            else:
                self.presets_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_wheel(_event=None):
            self.presets_canvas.bind_all("<MouseWheel>", on_mousewheel)
            self.presets_canvas.bind_all("<Button-4>", on_mousewheel)
            self.presets_canvas.bind_all("<Button-5>", on_mousewheel)

        def unbind_wheel(_event=None):
            self.presets_canvas.unbind_all("<MouseWheel>")
            self.presets_canvas.unbind_all("<Button-4>")
            self.presets_canvas.unbind_all("<Button-5>")

        self.presets_canvas.bind("<Enter>", bind_wheel)
        self.presets_canvas.bind("<Leave>", unbind_wheel)
        self.presets_scrollable_frame.bind("<Enter>", bind_wheel)
        self.presets_scrollable_frame.bind("<Leave>", unbind_wheel)

    def refresh_preset_buttons(self) -> None:
        """Refresh the preset buttons display."""
        # Clear existing buttons
        for widget in self.presets_scrollable_frame.winfo_children():
            widget.destroy()

        presets = self.config.get_presets()

        if not presets:
            ttk.Label(
                self.presets_scrollable_frame,
                text="No presets saved. Create presets from other tabs.",
                foreground="gray"
            ).pack(pady=20)
            return

        # Create preset buttons in grid
        row_frame = None
        for i, preset in enumerate(presets):
            if i % 4 == 0:
                row_frame = ttk.Frame(self.presets_scrollable_frame)
                row_frame.pack(fill=tk.X, pady=(0, 5))

            self._create_preset_button(row_frame, preset, i)

    def _create_preset_button(
        self,
        parent,
        preset: Dict[str, Any],
        index: int
    ) -> None:
        """Create a single preset button."""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(side=tk.LEFT, padx=(0, 5), pady=2)

        # Main button
        btn_text = preset.get('name', 'Preset')[:15]
        preset_type = preset.get('type', 'unknown')

        # Type indicator
        type_icons = {
            'text': 'T',
            'image': 'I',
            'clock': 'C',
            'stock': '$',
            'youtube': 'Y',
            'weather': 'W',
            'animation': 'A',
            'teams': 'M',
        }
        icon = type_icons.get(preset_type, '?')

        btn = ttk.Button(
            btn_frame,
            text=f"[{icon}] {btn_text}",
            command=lambda p=preset: self._execute_preset(p),
            width=18
        )
        btn.pack(side=tk.TOP)

        # Context menu
        menu = tk.Menu(btn, tearoff=0)
        menu.add_command(
            label="Edit",
            command=lambda p=preset, idx=index: self._edit_preset(p, idx)
        )
        menu.add_command(
            label="Delete",
            command=lambda idx=index: self._delete_preset(idx)
        )
        menu.add_separator()
        menu.add_command(
            label="Add to Playlist",
            command=lambda p=preset: self._add_to_playlist(p)
        )

        btn.bind("<Button-3>", lambda e, m=menu: m.post(e.x_root, e.y_root))

    def _execute_preset(self, preset: Dict[str, Any]) -> None:
        """Execute a preset."""
        if not self.state.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first")
            return

        if self.on_execute_preset:
            self.on_execute_preset(preset)

    def _edit_preset(self, preset: Dict[str, Any], index: int) -> None:
        """Edit a preset."""
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title("Edit Preset")
        dialog.geometry("400x150")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ttk.Label(dialog, text="Preset Name:").pack(pady=(20, 5))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=(0, 10))
        name_entry.insert(0, preset.get('name', ''))
        name_entry.focus()
        name_entry.select_range(0, tk.END)

        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("No Name", "Please enter a preset name")
                return

            preset['name'] = name
            self.config.update_preset(index, preset)
            self.refresh_preset_buttons()
            dialog.destroy()

        ttk.Button(dialog, text="Save", command=save).pack(pady=10)

    def _delete_preset(self, index: int) -> None:
        """Delete a preset."""
        if messagebox.askyesno("Confirm", "Delete this preset?"):
            self.config.remove_preset(index)
            self.refresh_preset_buttons()

    def _add_to_playlist(self, preset: Dict[str, Any]) -> None:
        """Add a preset to the playlist."""
        self.playlist.append({
            'preset': preset,
            'duration': 30
        })
        messagebox.showinfo("Added", f"Added '{preset.get('name')}' to playlist")

    # Playlist methods

    def play_playlist(self) -> None:
        """Start or resume playlist playback."""
        if not self.playlist:
            messagebox.showwarning("Empty Playlist", "Please add presets to the playlist first")
            return

        if not self.state.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first")
            return

        if self.playlist_paused:
            self.playlist_paused = False
            self.playlist_status_var.set(f"Playing: {self.playlist_index + 1}/{len(self.playlist)}")
            self._play_current()
        else:
            self.playlist_running = True
            self.playlist_paused = False
            self.playlist_index = 0
            self.playlist_status_var.set(f"Playing: 1/{len(self.playlist)}")
            self._play_current()

    def _play_current(self) -> None:
        """Play the current playlist item."""
        if not self.playlist_running or self.playlist_paused:
            return

        if self.playlist_index >= len(self.playlist):
            # Loop back to start
            self.playlist_index = 0

        item = self.playlist[self.playlist_index]
        preset = item['preset']
        duration = item.get('duration', 30) * 1000

        # Execute the preset
        if self.on_execute_preset:
            self.on_execute_preset(preset)

        self.playlist_status_var.set(
            f"Playing: {self.playlist_index + 1}/{len(self.playlist)} - {preset.get('name', 'Preset')}"
        )

        # Schedule next
        self.playlist_index += 1
        self.timers.schedule('playlist', duration, self._play_current)

    def pause_playlist(self) -> None:
        """Pause playlist playback."""
        if self.playlist_running:
            self.playlist_paused = True
            self.timers.cancel('playlist')
            self.playlist_status_var.set("Playlist: Paused")

    def stop_playlist(self) -> None:
        """Stop playlist playback."""
        self.playlist_running = False
        self.playlist_paused = False
        self.playlist_index = 0
        self.timers.cancel('playlist')
        self.playlist_status_var.set("Playlist: Stopped")

    def edit_playlist(self) -> None:
        """Open playlist editor dialog."""
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title("Edit Playlist")
        dialog.geometry("500x400")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Playlist listbox
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        listbox = tk.Listbox(list_frame, height=15)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.configure(yscrollcommand=scrollbar.set)

        def refresh_list():
            listbox.delete(0, tk.END)
            for i, item in enumerate(self.playlist):
                name = item['preset'].get('name', 'Preset')
                duration = item.get('duration', 30)
                listbox.insert(tk.END, f"{i+1}. {name} ({duration}s)")

        refresh_list()

        # Controls
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def move_up():
            sel = listbox.curselection()
            if sel and sel[0] > 0:
                idx = sel[0]
                self.playlist[idx], self.playlist[idx-1] = self.playlist[idx-1], self.playlist[idx]
                refresh_list()
                listbox.selection_set(idx-1)

        def move_down():
            sel = listbox.curselection()
            if sel and sel[0] < len(self.playlist) - 1:
                idx = sel[0]
                self.playlist[idx], self.playlist[idx+1] = self.playlist[idx+1], self.playlist[idx]
                refresh_list()
                listbox.selection_set(idx+1)

        def remove():
            sel = listbox.curselection()
            if sel:
                del self.playlist[sel[0]]
                refresh_list()

        def set_duration():
            sel = listbox.curselection()
            if not sel:
                return

            dur_dialog = tk.Toplevel(dialog)
            dur_dialog.title("Set Duration")
            dur_dialog.geometry("250x100")
            dur_dialog.transient(dialog)
            dur_dialog.grab_set()

            ttk.Label(dur_dialog, text="Duration (seconds):").pack(pady=(10, 5))
            dur_var = tk.IntVar(value=self.playlist[sel[0]].get('duration', 30))
            ttk.Spinbox(dur_dialog, from_=5, to=300, textvariable=dur_var, width=10).pack()

            def save_dur():
                self.playlist[sel[0]]['duration'] = dur_var.get()
                refresh_list()
                dur_dialog.destroy()

            ttk.Button(dur_dialog, text="OK", command=save_dur).pack(pady=10)

        ttk.Button(btn_frame, text="Move Up", command=move_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Move Down", command=move_down).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Remove", command=remove).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Set Duration", command=set_duration).pack(side=tk.LEFT)

        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def save_playlist(self) -> None:
        """Save playlist to file."""
        if not self.playlist:
            messagebox.showwarning("Empty", "Playlist is empty")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Playlist"
        )

        if path:
            try:
                data = {
                    'name': os.path.basename(path),
                    'items': self.playlist
                }
                with open(path, 'w') as f:
                    json.dump(data, f, indent=2)
                self.current_playlist_file = path
                self.current_playlist_name_var.set(os.path.basename(path))
                messagebox.showinfo("Saved", "Playlist saved successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")

    def load_playlist_dialog(self) -> None:
        """Load playlist from file."""
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Playlist"
        )

        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self.playlist = data.get('items', [])
                self.current_playlist_file = path
                self.current_playlist_name_var.set(data.get('name', os.path.basename(path)))
                messagebox.showinfo("Loaded", f"Loaded {len(self.playlist)} items")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")

    def import_presets(self) -> None:
        """Import presets from file."""
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import Presets"
        )

        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)

                imported = data if isinstance(data, list) else data.get('presets', [])
                for preset in imported:
                    self.config.add_preset(preset)

                self.refresh_preset_buttons()
                messagebox.showinfo("Imported", f"Imported {len(imported)} presets")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import: {e}")

    def export_presets(self) -> None:
        """Export presets to file."""
        presets = self.config.get_presets()
        if not presets:
            messagebox.showwarning("No Presets", "No presets to export")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Presets"
        )

        if path:
            try:
                with open(path, 'w') as f:
                    json.dump(presets, f, indent=2)
                messagebox.showinfo("Exported", f"Exported {len(presets)} presets")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
