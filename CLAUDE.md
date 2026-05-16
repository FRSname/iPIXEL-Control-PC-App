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

The Qt UI shares the framework-agnostic layers — `core/config.py`, `core/events.py`, `services/sprite_font.py`, `services/animation_generator.py`, and the pure helper functions in `services/stock_service.py` / `weather_service.py` / `youtube_service.py` / `services/instagram_service.py` (the `format_*` functions, `get_stock_color`, `_format_large_number`, `fetch_follower_count`, `refresh_long_lived_token`). It does **NOT** share `core/device.py` (Tkinter-bound) or anything under `ipixel_controller/ui/` or `ipixel_controller/features/`. Replacements live in `qt/device_bridge.py`, `qt/sprite_sender.py`, `qt/fetcher.py`.

The Instagram service is the only one that talks to its API via stdlib `urllib` rather than `requests` — keeps the dependency surface flat. New service modules should follow that pattern unless they need streaming or auth helpers `requests` provides.

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
- **Full-image BLE writes can't sustain < ~320 ms intervals.** `DeviceBridge._call` spawns a fresh worker thread per send (no internal queue), so rapid `send_image` calls race the pypixelcolor client. At intervals shorter than ~320 ms the panel times out, two failures in a row trip the disconnect guard above, and the panel goes blank mid-animation. `SpriteSender` scrolls happily at 120 ms because each frame is a small crop on a single owned timer; full-frame animations elsewhere need to space writes out (Instagram page uses 320–500 ms per frame with a single-shot `QTimer` that reschedules itself with the next interval).
- **Instagram icon layout requires a sprite font selected.** The composite needs to render the count *on top of* the icon canvas, which means the count text must come back as a PIL image from `SpriteFontService.render_text_line` — `device.send_text` would overwrite the panel slot rather than composite. The page surfaces a clear error if no sprite font is selected in icon mode.

## Config and state on disk

All in the working directory (== app folder when frozen):

- `ipixel_settings.json` — UI prefs, last-used device, sprite-font library
- `ipixel_presets.json` — saved presets (list)
- `ipixel_secrets.json` — API keys (YouTube `youtube_api_key`, OpenWeatherMap `weather_api_key`, Instagram Graph API `ig_user_id` / `ig_access_token` / `ig_app_id` / `ig_app_secret`). **Gitignored.** For Instagram: `ig_user_id` is the 17-digit IG Business Account ID, `ig_access_token` is a long-lived User Token or a non-expiring System User token; the `ig_app_*` pair is only needed if the page's "Refresh token" button is used (long-lived tokens expire after 60 days).
- `playlists/*.json` — playlists in the legacy shape `{"name", "items":[{"preset_name", "duration"}]}`. `qt.playlist.resolve_preset` looks items up by `preset_name` against the configured presets.
- `Gallery/Sprites/*.png` — sprite fonts and weather icons. The Weather page composites `Sunny.png` / `Cloudy.png` / `Rainy.png` / `Snow.png` / `SunCloudy.png` / `Atmospheric.png` / `Thunderstorm.png` + `Celsius.png` + `Temp_plus.png` / `Temp_minus.png` into a 64×16 panel image.

`utils/paths.resolve_asset_path` resolves relative paths against `get_app_dir()`, which returns `sys.executable`'s folder when frozen and the repo root in dev. Use it whenever you read assets so PyInstaller bundles work.

## ESP32 standalone firmware (`esp32-firmware/`)

Separate project — Arduino/PlatformIO, no shared code with the desktop app. It's a single-purpose "smart panel" companion: ESP32-WROOM-32U joins Wi-Fi, fetches Instagram follower counts itself, BLE-streams `send_image` frames to the panel. Same panel hardware, same `pypixelcolor` wire protocol; the protocol logic was reverse-engineered from the installed Python package at `C:\Users\filip.raszyk\AppData\Roaming\Python\Python314\site-packages\pypixelcolor\` — read that source when changing framing/handshake, not docs.

### Build and flash (PlatformIO)

```
Upload                       # firmware (src/) — picks up all .cpp/.h changes
Upload Filesystem Image      # data/index.html — separate flash partition; required after every data/ edit
Monitor                      # serial @ 115200, prints [ble]/[ig]/[cfg]/[wifi] lines
```

Both upload actions are separate buttons in the PIO toolbar — forgetting "Upload Filesystem Image" after editing `data/index.html` is the #1 reason "rebuilt but nothing changed" reports come in (the JS keeps posting the old format).

`platformio.ini` pins `board_build.partitions = min_spiffs.csv`. The default ESP32 partition gives the app only 1.3 MB, which overflows once NimBLE + WiFi + AsyncWebServer + WiFiManager are all linked — `min_spiffs` bumps it to 1.9 MB. Switching partition layouts moves the LittleFS region, so the first Upload after a partition change needs an Upload Filesystem Image too.

Boot-mode error 0x13 on Upload = auto-reset failed on this WROOM-32U board: hold BOOT, tap EN, release BOOT, retry Upload.

### Architecture

```
src/main.cpp              setup() → WiFiManager.autoConnect("iPixel-Setup") (AP fallback if
                           saved network is gone) → webUiBegin → ipixelBleSetup.
                           loop() → ipixelBleTick (10 s reconnect cadence after first immediate
                           attempt) → IG fetch (refreshSec) → animateTo → push frame.
src/web_ui.cpp            ESPAsyncWebServer on :80. Serves index.html from LittleFS.
                           Endpoints: GET /api/config, POST /api/config (FORM-encoded — NOT JSON;
                           AsyncJson has body-handler ordering issues and ArduinoJson 7 dropped the
                           old helpers), GET /api/status, POST /api/scan/start, GET /api/scan,
                           POST /api/wifi_reset. POST handlers set gFetchNow / gWifiReset so main
                           loop can react without blocking the web task.
src/ipixel_ble.cpp        NimBLE central. Name filter "LED_BLE_*" / "BGLight" / "B.K. Light".
                           Async scan into a mutex-protected results vector. tryConnect resolves
                           WRITE_UUID 0000fa02 + NOTIFY_UUID 0000fa03 by walking services.
src/png_encode.cpp        Hand-rolled LZ77 + fixed-Huffman deflate compressor producing a
                           standards-compliant PNG. ROM miniz doesn't help: only the decompressor
                           is in ROM, the compressor struct is ~265 KB. See protocol invariants
                           below for why we can't ship uncompressed PNGs.
src/renderer.cpp          64x16 RGB framebuffer drawer: bg fill, IG icon (with 1-bit alpha mask),
                           sprite font, slide-up tween between two text values.
src/instagram.cpp         WiFiClientSecure + setInsecure() + Graph API v21.0.
src/config.cpp            Preferences (NVS) namespace "ipx".
tools/sprites_to_h.py     Reads Gallery/Sprites/Instagram.png + TextSprite.png from the parent
                           desktop project, emits src/assets_icon.h (RGB + 1-bit alpha mask) and
                           src/assets_font.h (73-glyph × 7x16 1-bit font). Rerun after replacing
                           the source PNGs.
data/index.html           Mobile-first config page. URLSearchParams form-encoded POST to
                           /api/config (matches the server handler).
```

### Protocol invariants — every single one of these was a debugging session

Every item below is documented because we shipped a version that violated it and the panel silently failed:

- **PNG payload must be LZ77-compressed.** The panel ACKs the protocol frame with `notify len=5: 05 _ _ _ 03` (final-ack, "transfer complete") as long as the size + CRC line up — even when the PNG itself is malformed or oversized. A 3 KB literal-only PNG passed protocol checks but never rendered; PIL produces ~400 bytes for the same image and the panel renders it. `png_encode.cpp` uses an 8 KB sliding window, hash-chained matcher, fixed Huffman.
- **Fixed-Huffman length symbols start at code 1, not code 0.** RFC 1951 §3.2.6: 7-bit code 0 is the EOB symbol (256), length symbols 257–279 take codes 1–23. `emitLen` must use `sym - 256`, not `sym - 257`. Off-by-one means every length-3 match decodes as end-of-block and real zlib stops mid-stream with cryptic errors.
- **Send a get_device_info handshake right after subscribing.** Bytes `[8, 0, 1, 0x80, hour, minute, second, language=0]`. The panel will accept and ACK `send_image` frames before this happens but will not render their content. `pypixelcolor.DeviceSession.connect()` does it automatically; we have to do it ourselves.
- **The NOTIFY handler must signal the ack semaphore on any frame, not only `0x05`-prefixed ones.** The handshake reply is 11 bytes starting `0b 00 01 80 …`, the power-on ack starts `05 00 07 …`. If you filter on `data[0] == 0x05` before signalling, the handshake wait times out and `tryConnect` continues without the session being established. Keep the `g_ackFinal` check (5-byte `0x05 _ _ _ 3`) for the send_image final-ack flag, but always give the semaphore.
- **`send_image` framing for a single-window PNG.** `[2 LE prefix] [0x02, 0x00, option=0x00] [4 LE total PNG size] [4 LE CRC32 of PNG, LITTLE-endian] [0x00, save_slot=0] [png bytes]`, where `prefix = 2 + len(everything after prefix) = 15 + pngLen`. Chunk into 244-byte writes-with-response (matches `pypixelcolor.send_plan` `chunk_size=244` for MTU 247). Save slot 0 = ephemeral display (auto-shows, no `show_slot` needed).
- **First BLE connect attempt must fire immediately.** The retry guard `if (now - g_lastAttempt < RETRY_MS) return;` with `g_lastAttempt = 0` initial causes the very first `tick` to short-circuit for the first 10 s. Use a `g_attemptedOnce` flag so the gate only applies after the first try.
- **Repush `fb` when BLE transitions disconnected→connected.** `fetchAndDisplay` only calls `animateTo` when the follower count changes; on cold-boot the IG fetch usually wins the race to populate `fb` before BLE attaches, then the count stays the same and the panel never gets a frame. `main.cpp` watches the transition and re-sends the static frame.
- **Detect format-mode / colour changes in the same place as follower-count changes.** Compare the formatted text string (and `cfg.textColor` / `cfg.bgColor`) against the last-rendered values — not `r.followerCount` alone — or saving a new format mode in the web UI does nothing visible.
- **Icon transparency.** Don't flatten the IG icon onto black at conversion time; emit a 1-bit alpha mask (`IG_ICON_MASK` in `assets_icon.h`) and skip transparent pixels in `rendererDrawInstagramIcon`, otherwise the icon shows on a black square against any non-black `bgColor`.
- **WiFi reset works via WiFiManager's NVS slot.** `/api/wifi_reset` sets `gWifiReset`; the main loop calls `WiFi.disconnect(true, true)` + `WiFiManager().resetSettings()` and reboots. On next boot, `autoConnect("iPixel-Setup")` brings the captive-portal AP up since no creds are saved.
- **The MAC the user pastes / clicks-to-pick uses `BLE_ADDR_PUBLIC`.** iPixel panels advertise as public addresses (not random). Passing the wrong type to `NimBLEAddress` silently fails to connect.

### On-device storage

- NVS namespace `ipx` (`config.cpp`): `ig_id`, `ig_tok`, `refresh`, `fmt`, `fg`, `bg`, `mac`. Set/read via `Preferences`. Min refresh 60 s enforced on load + save.
- LittleFS: `data/index.html` only. Anything else here flashes with Upload Filesystem Image too.
- WiFiManager keeps its own NVS slot for the SSID/password.

### When the panel doesn't display anything

In order — these are the failure modes we've hit, ranked by likelihood:

1. Forgot Upload Filesystem Image after editing `data/index.html` (saves do nothing, format swatches do nothing).
2. Forgot the get_device_info handshake (BLE connects + `send_image` ACKs with `05 _ _ _ 03` but panel is stuck on its idle screen).
3. PNG encoder regression (re-verify with `python -c "from PIL import Image; ..."` against the `[ble] PNG dump` serial output).
4. Browser cached an older `index.html` — hard refresh.

## See also

- [AGENTS.md](AGENTS.md) — porting recipes, monolith retirement plan, layer breakdown.
- [README.md](README.md) — user-facing feature docs (still references the legacy launch flow).
- [esp32-firmware/README.md](esp32-firmware/README.md) — firmware-side build/flash notes.
