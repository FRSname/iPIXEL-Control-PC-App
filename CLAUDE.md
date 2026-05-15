# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Windows desktop app that controls iPixel BLE LED matrix panels (BGLight / B.K. Light / generic `LED_BLE_*`). Built on the [`pypixelcolor`](https://github.com/lucagoc/pypixelcolor) protocol library + [`bleak`](https://github.com/hbldh/bleak) BLE transport. Targets 64×16 panels.

## Three coexisting UIs — read this before editing anything

| Layer | Entry | Status |
| --- | --- | --- |
| Monolith Tkinter (legacy) | [ipixel_controller.py](ipixel_controller.py) (6000+ lines), launched by [run.py](run.py) / [run.bat](run.bat) | Still functional, not the migration target |
| Modular Tkinter (mid-refactor) | [ipixel_controller/](ipixel_controller/) → [app.py](ipixel_controller/app.py), launched by `python -m ipixel_controller` | Stalled; do not add features |
| **PySide6/Qt (current target)** | [ipixel_controller/qt/](ipixel_controller/qt/), launched by `python run_qt.py` or `python -m ipixel_controller.qt` | **All new UI work goes here** |

The Qt UI shares the framework-agnostic layers — `core/config.py`, `core/events.py`, `services/sprite_font.py`, `services/animation_generator.py`, and the pure helper functions in `services/stock_service.py` / `weather_service.py` / `youtube_service.py` (the `format_*` functions, `get_stock_color`, `_format_large_number`). It does **NOT** share `core/device.py` (Tkinter-bound) or anything under `ipixel_controller/ui/` or `ipixel_controller/features/`. Replacements live in `qt/device_bridge.py`, `qt/sprite_sender.py`, `qt/fetcher.py`.

When the user reports a bug, check which UI they're running. The monolith and the Qt UI both exist on disk and can be launched independently.

## Commands

```bash
pip install -r requirements.txt    # PySide6 + bleak + pypixelcolor + service deps
python run_qt.py                   # dev launch (Qt UI)
python build_exe.py                # PyInstaller one-folder build + Start Menu shortcut prompt
python build_exe.py --clean        # wipe build/ + dist/ first
python build_exe.py --no-shortcut  # build only, skip shortcut prompt
```

There is no test suite. Syntax-check the Qt package after edits:

```bash
python -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('ipixel_controller/qt').rglob('*.py')]"
```

`PySide6-Addons` is optional — required only for the embedded Pixilart editor on the Draw page. Without it the Draw page falls back to opening the user's default browser.

The PyInstaller spec ([iPixelController.spec](iPixelController.spec)) targets `run_qt.py`, excludes the Tk runtime, and pulls in `QtWebEngineWidgets` / `QtWebEngineCore` best-effort.

## Qt architecture

```
qt/app.py             QApplication + stylesheet + ConfigManager → MainWindow
qt/main_window.py     QMainWindow with sidebar nav + content stack + ConnectionBar + status bar
qt/device_bridge.py   BLE wrapper: owns its asyncio loop on a background thread,
                      exposes operations as plain methods and results as Qt signals
qt/sprite_sender.py   Render-with-font → save temp PNG → device.send_image. Owns
                      a QTimer for scrolling. Used by every text-based page.
qt/fetcher.py         BackgroundFetcher: runs any blocking function in a thread,
                      surfaces success/failure via Qt signals. Used by Stock/Weather/YouTube.
qt/playlist.py        PlaylistPlayer: cycles preset items on a QTimer.
qt/theme.py           Single QSS string applied at QApplication level.
qt/pages/             One Page subclass per feature.
qt/widgets/           Card, Sidebar, ConnectionBar, ColorButton, SpriteFontPicker,
                      ColorPickerDialog.
```

### Page contract

Every feature page extends `qt.pages.base.Page` and is constructed in `MainWindow._build_pages` with `(device_bridge, config_manager, sprite_font_service)`. The base class provides:

- `content_layout()` for stacking cards inside the page
- `take_remaining_space(widget)` to give a widget the remaining vertical space (used by the embedded webview in Draw)
- `on_connection_changed(connected: bool)` — main window broadcasts this to every page on connect/disconnect
- `on_shown()` / `on_hidden()` — called by `MainWindow._show` when the page becomes/stops being visible

Pages that hold a `SpriteFontPicker` should also implement `refresh_font_list(names)` so the Settings page's library editor can push updates live.

Presets are saved/loaded via `ConfigManager.add_preset` and dispatched through `MainWindow._run_preset` → `page.execute_preset(preset)`. Preset dicts always have a `type` key matching the feature id; that's how the dispatcher finds the page.

### Adding a new feature page (recipe)

See [AGENTS.md](AGENTS.md) → "How to port a feature to Qt". Short version:

1. New `qt/pages/<feature>_page.py` subclassing `Page`.
2. Inject `DeviceBridge` for panel writes, `ConfigManager` for persistence, `SpriteFontService` if it renders text.
3. Use `qt.widgets.Card` for grouping; `ColorButton`, `SpriteFontPicker` for inputs.
4. Implement `_send()`, `_save_preset()`, `execute_preset(preset)`.
5. Register the page in `qt/pages/__init__.py`, add the id to `MainWindow.PORTED_FEATURES` and the row to `NAV_FEATURES`, build it in `_build_pages`.

## Non-obvious invariants

These are bugs we have already hit; don't reintroduce them:

- **`pypixelcolor.send_text` rejects `#`-prefixed hex.** `DeviceBridge.send_text` strips the leading `#` on `color` / `bg_color` kwargs. Don't bypass the bridge or you'll re-hit `Invalid color hex: #ff0000`.
- **Sprite-font text goes through `device.send_image`, not `send_text`.** That's why background colours (including white) display correctly on panels whose firmware dims `send_text` backgrounds. The `SpriteSender` helper handles this; pages route through it whenever the user enables the sprite-font picker.
- **`QStackedWidget` children inherit the stack's height.** `Card` sets `QSizePolicy(Preferred, Maximum)` so it hugs its content; without that, cards inside Clock's mode stack would grow to the height of the tallest mode.
- **Widget stylesheets cascade to descendants, including child dialogs.** `ColorButton` scopes its rule to `QPushButton#ColorButton { ... }` and parents the picker dialog to `self.window()` rather than to itself — otherwise the selected swatch colour tinted the dialog background.
- **Don't use Qt's `QColorDialog` directly.** It inherits the app stylesheet and renders broken. Use `qt.widgets.color_picker_dialog.pick_color(initial, parent)`.
- **`time.toPython()` is Python `datetime`; `QDateTime` constructor needs `QDate` + `QTime`** (or 6 ints incl. seconds). The 5-int form does not exist in PySide6.
- **Construct widgets before connecting their signals + setting initial state.** Several Qt page constructors had `setChecked(True)` firing `toggled` before the slot's referenced widgets existed. The pattern in `ClockPage` is: build everything, then `for rb in radios: rb.toggled.connect(...)`, then `radios[0].setChecked(True)`.
- **`MainWindow._on_operation_failed` is non-modal on purpose.** A failing playlist would otherwise stack one `QMessageBox` per item. Errors go to the status bar; identical errors within 1 s coalesce; after 2 "no ack" / "no_answer" / "timeout" errors in a row the bridge disconnects and the home page's playlist player stops.

## Config and state on disk

All in the working directory (== app folder when frozen):

- `ipixel_settings.json` — UI prefs, last-used device, sprite-font library
- `ipixel_presets.json` — saved presets (list)
- `ipixel_secrets.json` — API keys (YouTube, OpenWeatherMap). **Gitignored.**
- `playlists/*.json` — playlists in the legacy shape `{"name", "items":[{"preset_name", "duration"}]}`. `qt.playlist.resolve_preset` looks items up by `preset_name` against the configured presets.
- `Gallery/Sprites/*.png` — sprite fonts and weather icons. The Weather page composites `Sunny.png` / `Cloudy.png` / `Rainy.png` / `Snow.png` / `SunCloudy.png` / `Atmospheric.png` / `Thunderstorm.png` + `Celsius.png` + `Temp_plus.png` / `Temp_minus.png` into a 64×16 panel image.

`utils/paths.resolve_asset_path` resolves relative paths against `get_app_dir()`, which returns `sys.executable`'s folder when frozen and the repo root in dev. Use it whenever you read assets so PyInstaller bundles work.

## See also

- [AGENTS.md](AGENTS.md) — porting recipes, monolith retirement plan, layer breakdown.
- [README.md](README.md) — user-facing feature docs (still references the legacy launch flow).
