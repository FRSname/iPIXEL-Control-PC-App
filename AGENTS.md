# Agent Notes (iPixel Controller)

This document is for other agents working on the project. It summarizes architecture, file layout, and common pitfalls.

## Current state: PySide6 migration in progress

The repo has THREE coexisting UI layers right now. Know which one you're in before editing.

| Layer | Entry point | Status |
| --- | --- | --- |
| Monolith Tkinter (legacy) | `ipixel_controller.py` (6063 lines), launched by `run.py` / `run.bat` | Production today; users still use this. Do not add features here. |
| Modular Tkinter | `ipixel_controller/` package (`app.py`, `core/`, `ui/`, `features/`), launched by `python -m ipixel_controller` | Refactor stalled; will be deleted after the Qt migration completes. Do not add features here either. |
| **PySide6 (target)** | `ipixel_controller/qt/` package, launched by `python -m ipixel_controller.qt` or `python run_qt.py` | **Active development.** All new UI work goes here. |

The Qt UI shares `core/` (config, events, state, timers) and `services/` with the Tkinter UIs — those layers are framework-agnostic. It does NOT share `ui/`, `features/`, or `core/device.py` (Tkinter-bound; replaced by `qt/device_bridge.py`).

### How to port a feature to Qt
1. Add a new `ipixel_controller/qt/pages/<feature>_page.py` subclassing `qt.pages.base.Page`.
2. Use `qt.widgets.Card` for grouping, `ColorButton` for colour pickers, `QSlider`/`QSpinBox` for numeric inputs.
3. Inject `DeviceBridge` (Qt-signal-based BLE wrapper) and `ConfigManager`.
4. Implement `_send()` for "Send to panel", `_save_preset()` for persistence, and `execute_preset(preset)` so home-page tiles can run it.
5. In `qt/main_window.py`: import the page, register it in `_build_pages()`, and add the feature id to `PORTED_FEATURES` so the sidebar marks it active.
6. Delete the matching `ipixel_controller/features/<feature>_feature.py` only after the Qt port is verified against a real device.

Ported so far: **Home (presets)**, **Text**, **Image**, **Clock** (built-in / custom / countdown), **Animations** (Game of Life / Matrix / Fire / Starfield / Plasma), **Stock**, **Weather**, **YouTube**, **Settings** (brightness/power/auto).

**Still missing on the Qt side (carried over from the legacy app):**
- Sprite-font rendering paths in Text / Clock / Stock / YouTube / Weather (Qt UI calls `device.send_text` only).
- Sprite-font library management in Settings (currently Tk-only).
- YouTube inline logo + Weather icon images.
- Playlist support in the Home page (preset auto-cycling).
- Teams presence feature (legacy `teams_monitoring` state).

### Build / launch
- Dev launch: `python run_qt.py`
- One-shot Windows build (PyInstaller + Start Menu shortcut): `python build_exe.py`
- Spec file: `iPixelController.spec` (excludes Tk runtime — saves a few MB)

### Monolith retirement plan
Once Image, Clock, Stock, YouTube, Weather, and Animations are ported and verified:
1. Delete `ipixel_controller.py`, `run.py`, `run.bat`, `convert_to_customtkinter.py`.
2. Delete `ipixel_controller/ui/` and `ipixel_controller/features/` and `ipixel_controller/core/device.py`.
3. Update README to point at `iPixelController.exe` / `run_qt.py`.

## Legacy project overview (will be removed)
- Tkinter desktop app controlling iPixel BLE LED panels.
- Primary entry point: `ipixel_controller.py`.
- Secondary launcher: `run.py`.
- Presets and settings are JSON files; assets are local images and sprite sheets.

## Key Files
- `ipixel_controller.py`: Main UI, device communication, rendering, timers.
- `ipixel_settings.json`: User settings (no secrets).
- `ipixel_presets.json`: Saved presets.
- `ipixel_secrets.json`: API keys (gitignored).
- `Gallery/`: bundled images, sprites, weather assets.
- `Gallery/Sprites/`: sprite sheets for text/clock/youtube.

## Secrets Handling
- API keys are stored in `ipixel_secrets.json`.
- Never commit keys; `.gitignore` already ignores `ipixel_secrets.json`.
- UI “Save Key” buttons write to secrets via `save_secrets()`.

## Asset Path Resolution
- Relative paths are resolved against the app folder using `_resolve_asset_path()`.
- Default assets live in `Gallery/` and `Gallery/Sprites/`.
- Use relative paths in settings/presets for portability.

## Sprite Fonts
- Managed via Settings → Sprite Fonts.
- Stored in `ipixel_settings.json` under `sprite_fonts`.
- Each entry: `{ name, path, order, cols }`.
- Default fonts are merged at startup by `_ensure_default_sprite_fonts()`.
- Use `_build_sprite_text_image()` or `_build_sprite_text_line_image()`.

### Glyph Orders
- Text fonts generally use:
  `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$%`
- Clock fonts use:
  `0123456789:`

## Timers and State
Common timers and their intent:
- `clock_timer`: live clock tick
- `text_static_timer`: static cycle for text
- `stock_static_timer`: static cycle for stocks
- `stock_refresh_timer`: background stock refresh
- `youtube_refresh_job`, `weather_refresh_job`: periodic refresh jobs
- `sprite_scroll_timer`: sprite scroll animation

When switching content, call `_stop_active_display_tasks()` to avoid old timers re-sending content.

## Display Send Flow
- Text, stocks, YouTube, weather may send sprite images or text via BLE.
- Sprite scroll uses `_start_sprite_scroll()`; remember to stop it when switching.
- For inline YouTube logo, 14x16 PNG is expected.

## Known Pitfalls
- Multiple timers can overlap and re-send content unless canceled.
- Avoid absolute file paths in settings/presets.
- Some panels render built-in text background too dim; use images for bright backgrounds.

## Development Notes
- Prefer minimal changes; avoid reformatting.
- Use `apply_patch` for edits.
- Update README when user-facing behavior changes.

## Running
- `python run.py`
- Dependencies in `requirements.txt`.

## Useful Sections in `ipixel_controller.py`
- Sprite font management: methods `_get_sprite_fonts`, `_ensure_default_sprite_fonts`, `_build_sprite_text_image`.
- Sending: `send_text`, `send_stock_to_display`, `send_youtube_to_display`, `send_weather_to_display`, `send_image`.
- Cleanup: `_stop_active_display_tasks`, `stop_live_clock`, `stop_stock_refresh`, `stop_animation`.
