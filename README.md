# iPixel LED Panel Controller

A desktop application + companion ESP32 firmware that drive iPixel Color BLE
LED matrix panels (BGLight, B.K. Light, and generic `LED_BLE_*` devices) from
a Windows PC or standalone over Wi-Fi.

![iPixel Controller](screenshot.png)

## What's in this repo

| Component | Path | Purpose |
| --- | --- | --- |
| **Qt desktop app (current)** | `ipixel_controller/qt/` + `run_qt.py` | The actively developed PySide6 UI. All new features land here. |
| Modular Tkinter (mid-refactor) | `ipixel_controller/` (non-`qt/`) | Transitional package; **frozen** — will be removed once Qt parity is final. |
| Monolith Tkinter (legacy) | `ipixel_controller.py` + `run.py` / `run.bat` | The original 6000-line app. Still launches; no new work here. |
| **ESP32 firmware** | `esp32-firmware/` | Standalone Instagram follower counter that drives a panel over BLE without needing a PC. |

If you are a returning user: launch the Qt app with `python run_qt.py`. The old
`run.bat` / `run.py` still work but point at the legacy monolith.

## Major refactor in 2026 — what changed

The codebase went through a big restructuring this year:

- **PySide6/Qt UI is now the primary frontend.** Everything visible to users —
  pages, sidebar, theming, color pickers, connection bar — lives under
  `ipixel_controller/qt/`. The legacy Tkinter monolith is kept on disk for
  fallback but receives no new features.
- **Framework-agnostic core extracted.** `core/config.py`, `core/events.py`,
  `services/sprite_font.py`, `services/animation_generator.py`, plus the pure
  helpers inside the Stock / Weather / YouTube / Instagram service modules are
  shared by both the Qt app and (where still used) the legacy Tk path.
- **BLE wrapper rewritten.** The Tkinter-coupled `core/device.py` was replaced
  by `qt/device_bridge.py` — a `DeviceBridge` that owns its own asyncio loop on
  a background thread and surfaces results as Qt signals. `qt/sprite_sender.py`,
  `qt/fetcher.py`, and `qt/playlist.py` build on top of it.
- **Sprite-font text now goes through `send_image`,** not `send_text`. This
  fixes the dim-background issue on panels whose firmware dims `send_text`
  backgrounds (white-on-anything actually looks white now).
- **New Instagram feature** — both as a Qt page (`qt/pages/instagram_page.py`)
  and as a standalone ESP32 firmware in `esp32-firmware/` (see below).
- **Embedded Pixilart editor** on the Draw page via `QtWebEngineWidgets` when
  `PySide6-Addons` is installed; falls back to the system browser otherwise.
- **Playlists** — cycle saved presets on a timer from the Home page
  (`qt/playlist.py`). Playlists are JSON files under `playlists/`.

Internal architecture, porting recipes, and known invariants are documented in
[CLAUDE.md](CLAUDE.md) and [AGENTS.md](AGENTS.md).

## Quick start (desktop app)

1. Install **Python 3.8+** from [python.org](https://www.python.org/downloads/)
   — tick **"Add Python to PATH"** during install.
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
   `PySide6-Addons` is optional; only needed if you want the embedded Pixilart
   editor on the Draw page (without it, Draw opens the system browser).
3. Launch the Qt UI:
   ```bash
   python run_qt.py
   ```
   Or, on Windows, after building with `python build_exe.py`, run the bundled
   `iPixelController.exe` from `dist/`.

### Building a standalone Windows .exe

```bash
python build_exe.py                 # PyInstaller one-folder build + Start Menu shortcut prompt
python build_exe.py --clean         # wipe build/ + dist/ first
python build_exe.py --no-shortcut   # build only, skip shortcut prompt
```

The spec ([iPixelController.spec](iPixelController.spec)) targets `run_qt.py`,
excludes the Tk runtime to save a few MB, and best-effort pulls in
`QtWebEngineWidgets` / `QtWebEngineCore` for the Draw page.

## Features (desktop app)

### Core
- Auto-scan for iPixel devices via Bluetooth LE
- Send text with customisable text colour, background colour, and sprite fonts
- Display images (PNG, JPG, GIF, BMP)
- Clock modes: built-in styles, custom time formats, countdown timers
- Preset system — save, recall, and cycle via playlists
- Brightness (1–100%) and power control

### Stock Market Display
Live prices via the free `yfinance` library (no API key). Smart formatting
(K/M notation), auto-colour based on direction.

### YouTube Stats
Subscribers display with an optional inline 14×16 logo. Requires a free
YouTube Data API v3 key.

### Weather
Current conditions + temperature from OpenWeatherMap. Composite icons:
`Sunny.png`, `Cloudy.png`, `Rainy.png`, `Snow.png`, `SunCloudy.png`,
`Atmospheric.png`, `Thunderstorm.png`, plus `Celsius.png` / `Temp_plus.png` /
`Temp_minus.png` — all bundled in `Gallery/Sprites/`. Requires a free
OpenWeatherMap API key.

### Instagram (NEW)
Show your Instagram Business follower count. Requires `ig_user_id` (the
17-digit IG Business Account ID) and `ig_access_token` (a long-lived User
Token or a non-expiring System User token). Optional `ig_app_id` /
`ig_app_secret` enable the page's "Refresh token" button (long-lived tokens
expire after 60 days). Icon-mode renders the count *on top of* the IG icon
canvas and requires a sprite font selected.

### Draw
Pixel-art editor embedded via `QtWebEngineWidgets` (when `PySide6-Addons` is
installed) or opened in the system browser. Output exports to PNG and feeds
into the Image / preset pipeline.

### Pixel-art Animations
Conway's Game of Life, Matrix Rain, Fire, Starfield, Plasma. Configurable
FPS, colour scheme, and duration.

### Playlists
Cycle a sequence of saved presets on a timer. Playlists live as JSON under
`playlists/` in the legacy shape `{"name", "items":[{"preset_name", "duration"}]}`.

## ESP32 firmware (`esp32-firmware/`)

A self-contained ESP32 firmware that polls Instagram followers over Wi-Fi and
pushes the result directly to an iPixel BLE panel — **no PC needed once
provisioned**. Useful if you want a permanent always-on counter.

### Capabilities
- WiFiManager captive portal for first-time Wi-Fi setup (AP name: `iPixel-Setup`).
- Mobile-friendly web UI served from LittleFS for configuration after the
  ESP32 joins your network.
- Instagram Graph API poller (configurable refresh interval, ≥ 60 s).
- 5×7 sprite-font renderer on a 64×16 framebuffer with slide-up tween
  animation when the count changes.
- NimBLE client that auto-connects to the panel by MAC (with scan-and-pick
  flow in the web UI).
- All settings persist in ESP32 NVS (Preferences) — survive power cycles.
- **Rotate display 180°** option for panels mounted upside-down. Mirrors the
  framebuffer in software just before BLE encoding; works with every render
  path (Instagram updates, tween frames, repush-on-reconnect).

### Hardware
- **MCU**: any ESP32 with at least 4 MB flash (developed against
  ESP32-WROOM-32U with external IPEX antenna).
- **Panel**: any pypixelcolor-compatible iPixel / BGLight / B.K. Light 64×16
  BLE panel.

### Installing the firmware

You need **VS Code** + the **PlatformIO IDE** extension. There is no
pre-built `.bin` distributed — the firmware is built from source so the
filesystem image (web UI) can be embedded.

1. Install [VS Code](https://code.visualstudio.com/) and search the
   Extensions marketplace for **PlatformIO IDE**. Install it. First launch
   takes a few minutes while PlatformIO downloads the toolchain.
2. Open the `esp32-firmware/` folder in VS Code (**File → Open Folder…**).
   PlatformIO will detect `platformio.ini` and finish setting up the project.
3. Plug the ESP32 board into USB. Windows should pick up the USB-to-serial
   driver automatically; if not, install the CP2102 / CH340 driver for your
   board.
4. In the PlatformIO sidebar (the alien icon on the left), open **Project
   Tasks → esp32dev → General**, then:
   - Click **Build** — compiles the firmware.
   - Click **Upload Filesystem Image** — flashes `data/index.html` (the web
     UI) to LittleFS. **Do this before, or any time you change the HTML.**
   - Click **Upload** — flashes the firmware itself.
5. Open **Monitor** (same Project Tasks panel) at 115200 baud to watch boot
   messages.

> **CLI alternative:** if you prefer the terminal, install PlatformIO Core
> (`pip install platformio`) and run from `esp32-firmware/`:
> ```bash
> pio run                  # build
> pio run -t uploadfs      # flash LittleFS (web UI)
> pio run -t upload        # flash firmware
> pio device monitor       # serial monitor
> ```

### First-time provisioning (after flashing)

On first boot the ESP32 has no Wi-Fi credentials, so it starts an open AP:

1. On your phone, connect to the Wi-Fi network **`iPixel-Setup`** (no password).
2. A captive portal opens automatically — pick your home Wi-Fi, enter the
   password, save. The ESP32 reboots and joins.
3. Watch the serial monitor for the IP address, e.g. `[wifi] connected,
   IP=192.168.1.42`.
4. On your phone (or any device on the same network), open
   `http://<that-ip>/` in a browser.
5. Configure:
   - **Instagram Business Account ID** (17-digit numeric, starts with `17841…`)
   - **Access Token** — long-lived User Token or non-expiring System User
     token (see the desktop app's Instagram tab or
     [Graph API Explorer](https://developers.facebook.com/tools/explorer))
   - **Refresh interval** (seconds, minimum 60)
   - **Display format**, **text colour**, **background colour**
   - **Panel MAC** — click **Scan for panels**, then tap the device that
     matches your panel
   - **Rotate display 180°** — check if your panel is mounted upside-down
6. Tap **Save**. The ESP32 fetches the follower count immediately and pushes
   it to the panel; all settings persist across reboots in NVS.

### Wi-Fi reset

If you move the ESP32 to a different network, open the web UI and tap
**Forget Wi-Fi & reboot**. The ESP32 will come back up as the `iPixel-Setup`
AP for re-provisioning.

### Firmware layout

```
esp32-firmware/
├── platformio.ini             # board + libraries
├── data/index.html            # web UI (flashed to LittleFS via uploadfs)
├── src/
│   ├── main.cpp               # orchestration, poll loop, animation driver
│   ├── config.{h,cpp}         # NVS-backed settings (incl. rotate180)
│   ├── web_ui.{h,cpp}         # HTTP + JSON API + scan endpoints
│   ├── instagram.{h,cpp}      # HTTPS Graph API fetch
│   ├── renderer.{h,cpp}       # 5×7 font → 64×16 RGB buffer + tween
│   ├── ipixel_ble.{h,cpp}     # NimBLE client + frame encoder
│   └── png_encode.{h,cpp}     # 64×16 RGB → PNG (for send_image framing)
```

See [esp32-firmware/README.md](esp32-firmware/README.md) for milestone
history and protocol details.

## Requirements (desktop app)

- Windows 10/11 (with Bluetooth LE support)
- Python 3.8 or higher
- Bluetooth LE adapter (built-in or USB dongle)
- An iPixel Color compatible LED panel

## Configuration files

All in the working directory (or the app folder when frozen with PyInstaller):

| File | Purpose |
| --- | --- |
| `ipixel_settings.json` | UI prefs, last-used device, sprite-font library |
| `ipixel_presets.json` | Saved presets |
| `ipixel_secrets.json` | API keys — `youtube_api_key`, `weather_api_key`, `ig_user_id`, `ig_access_token`, optional `ig_app_id` / `ig_app_secret`. **Gitignored.** |
| `playlists/*.json` | Playlist definitions |
| `Gallery/Sprites/*.png` | Sprite fonts + weather/Instagram icons |

API keys are entered through the Qt UI (Instagram / YouTube / Weather pages)
and saved into `ipixel_secrets.json` for you.

## Troubleshooting

### Desktop app

- **Device not found during scan** — power-cycle the panel, confirm Bluetooth
  is on, ensure no other app (vendor app, ESP32 firmware) is currently
  connected, move closer to the PC.
- **Connection failed** — close the official vendor app, remove the device
  in Windows Settings → Bluetooth & devices, then re-scan.
- **`ModuleNotFoundError`** — re-run `python -m pip install -r requirements.txt`.
- **Background colour looks dim** — this is a firmware quirk of some panels
  with `send_text`. Sprite-font text in the Qt app routes through
  `send_image` and renders backgrounds correctly. For fully custom looks, use
  an image preset.

### ESP32 firmware

- **`iPixel-Setup` AP doesn't appear** — wait ~10 s after power-on for the
  WiFiManager portal to come up; if it still doesn't appear, check the serial
  monitor for boot errors.
- **Web UI loads but says "IG: …"** — confirm the access token is valid in
  Graph API Explorer; tokens expire after 60 days unless they're System User
  tokens.
- **Panel stays blank but BLE shows "connected"** — make sure the selected
  panel MAC actually matches the one near you; the scan list sorts by RSSI.
- **Display is upside-down** — tick the "Rotate display 180°" option in the
  web UI and save.

## Technical details

### Supported devices
LED panels using the iPixel Color protocol over BLE: BGLight LED Pixel
Boards, B.K. Light LED Pixel Board (Action stores), generic `LED_BLE_*` devices.

### Protocol
- **Transport**: Bluetooth Low Energy
- **Write UUID**: `0000fa02-0000-1000-8000-00805f9b34fb`
- **Notify UUID**: `0000fa03-0000-1000-8000-00805f9b34fb`
- **Library**: built on [pypixelcolor](https://github.com/lucagoc/pypixelcolor)

## Credits

- Built on [pypixelcolor](https://github.com/lucagoc/pypixelcolor) by lucagoc.
- BLE transport via [bleak](https://github.com/hbldh/bleak) (desktop) and
  [NimBLE-Arduino](https://github.com/h2zero/NimBLE-Arduino) (ESP32).
- Protocol docs cross-referenced against the
  [ha-ipixel-color](https://github.com/cagcoach/ha-ipixel-color) Home
  Assistant integration.

## License

Provided as-is for personal use. Not affiliated with iPixel or the original
device manufacturers.
