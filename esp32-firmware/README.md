# iPixel IG Counter — ESP32 firmware

Self-contained ESP32 firmware that polls Instagram followers count over WiFi
and pushes the result to an iPixel BLE LED panel.

## Hardware

- **MCU**: ESP32-WROOM-32U (external IPEX antenna)
- **Panel**: any pypixelcolor-compatible iPixel / BGLight / B.K. Light 64×16 BLE panel

## First-time setup

1. Install [VS Code](https://code.visualstudio.com/) and the **PlatformIO IDE** extension.
2. Open this folder (`esp32-firmware/`) as a workspace in VS Code.
3. Plug the ESP32 over USB. PlatformIO auto-detects the port.
4. Click **PlatformIO: Build** (✓ icon, bottom toolbar).
5. Click **Upload Filesystem Image** in the PlatformIO sidebar (Platform → Upload Filesystem Image) — this flashes `data/index.html` to LittleFS.
6. Click **PlatformIO: Upload** (→ icon).
7. Open **Serial Monitor** (plug icon). Watch boot messages.

## Provisioning

On first boot the ESP32 has no WiFi creds, so it starts an AP named **`iPixel-Setup`**.

1. Connect your phone to that AP (no password).
2. Captive portal opens automatically; pick your home WiFi, enter password, save.
3. ESP32 reboots, joins your WiFi, prints its IP over serial.
4. From your phone, browse to `http://<that-ip>/`.
5. Enter Instagram Business Account ID + Access Token, set refresh interval, save.

## Milestones

- [x] WiFi captive portal + persistent settings (NVS)
- [x] Web config UI served from LittleFS (mobile-friendly)
- [x] Instagram Graph API poller (`graph.facebook.com/v21.0/{id}?fields=followers_count`)
- [x] 5×7 sprite-font renderer on a 64×16 framebuffer
- [x] Slide-up tween animation when the count changes
- [ ] **BLE client** — NimBLE connect, MTU negotiation, scan filter
- [ ] **PNG encoder** for the 64×16 framebuffer
- [ ] **pypixelcolor `send_image` framing** — see `src/ipixel_ble.cpp` for the protocol reference

## Project layout

```
platformio.ini             # board + libraries
data/index.html            # web UI (flashed to LittleFS)
src/main.cpp               # orchestration, poll loop, animation driver
src/config.{h,cpp}         # NVS-backed settings
src/web_ui.{h,cpp}         # HTTP + JSON API
src/instagram.{h,cpp}      # HTTPS Graph API fetch
src/renderer.{h,cpp}       # 5x7 font → 64x16 RGB buffer + tween
src/ipixel_ble.{h,cpp}     # BLE client (stub — milestone 2)
```

## Getting an Instagram Business Account ID + Access Token

Same flow as the parent desktop app. See `ipixel_controller/services/instagram_service.py`
header doctring for the short version, or the Graph API Explorer at
[developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer).
A non-expiring System User token is the most maintenance-free option.
