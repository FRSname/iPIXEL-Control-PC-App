# Agent Notes (iPixel Controller)

This document is for other agents working on the project. It summarizes architecture, file layout, and common pitfalls.

## Project Overview
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
