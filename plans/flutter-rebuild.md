# Blueprint: Flutter Multiplatform Rebuild of iPixel Controller

- **Objective**: Rebuild the Python/PySide6 desktop app as a Flutter app for Windows, macOS, Linux, iOS, Android. Core-first scope.
- **Repo**: `github.com/FRSname/iPIXEL-Control-PC-App` (branch `main`), workflow mode: full (git + gh authenticated).
- **New code lives in**: `flutter_app/` at repo root (sibling of `esp32-firmware/` — same subproject pattern).
- **Dev machine**: macOS, Xcode 26.5 installed, Flutter NOT yet installed. Windows builds via GitHub Actions (cannot cross-compile from macOS).
- **Created**: 2026-07-21. **Revised**: 2026-07-21 after adversarial review (see mutation log).

## Global context brief (read this before any step)

The app drives iPixel/BGLight/B.K. Light 64×16 BLE LED matrix panels. Existing implementations to reference (do not modify them):

- `CLAUDE.md` §"Non-obvious invariants" and §"Protocol invariants" — hard-won protocol facts.
- `esp32-firmware/src/ipixel_ble.cpp` — C++ reference of the full BLE flow (framing at lines ~296–309, handshake ~203, power `[5,0,7,1,on]` ~220, ack handling ~73). Contains NO brightness command — see S1 note.
- `ipixel_controller/services/sprite_font.py` — sprite-font rendering reference.
- `ipixel_controller/core/config.py` — persistence reference.
- `ipixel_controller/qt/` — UX reference (pages, widgets, flows).

### BLE transport decision (made at plan time, binding)

`flutter_blue_plus` supports Android/iOS/macOS only — NOT Windows or Linux. Since the objective requires all five platforms, the plan uses **`universal_ble`** (single API: Android, iOS, macOS, Windows, Linux, web) behind a thin `BleTransport` interface of our own. The interface keeps a escape hatch: if `universal_ble` proves unreliable on any platform, swap that platform's backend (e.g. `flutter_blue_plus` mobile+macOS, `win_ble` Windows, BlueZ/`bluez` Linux) without touching feature code. S4 must prove scan+connect on macOS; Windows and Linux BLE proof happens in S11, BEFORE release packaging.

### Protocol facts (source of truth for the Dart port)

- Write characteristic `0000fa02-0000-1000-8000-00805f9b34fb`, notify `0000fa03-0000-1000-8000-00805f9b34fb`.
- Scan name filters (superset from firmware, more correct than the Python desktop bridge): prefixes `LED_BLE_`, `LED-BLE-`; names containing `BGLight`, `B.K. Light`, `BK Light`.
- **Handshake**: immediately after subscribing to notify, send `[8, 0, 1, 0x80, hour, minute, second, 0]` (get_device_info + time sync). Panel ACKs `send_image` even without it but never renders — this must be part of connect, not optional.
- **Notify handling**: signal the pending-ack completer on ANY notify frame (handshake reply is 11 bytes `0b 00 01 80 …`, power ack starts `05 00 07 …`). Separately track the send_image final-ack: `len >= 5 && data[0]==0x05 && data[4]==0x03` (firmware uses `>=`, not `==` — trailing bytes are possible).
- **send_image framing** (single window, ephemeral slot 0):
  `[u16 LE prefix = 15 + pngLen] [0x02, 0x00, 0x00] [u32 LE pngLen] [u32 LE crc32(png)] [0x00, 0x00] [png bytes]`
- **Chunking is MTU-adaptive**: `chunkSize = min(244, negotiatedMtu - 3)`. 244 assumes MTU 247; Android needs an explicit `requestMtu(247)`, CoreBluetooth (iOS/macOS) negotiates automatically and often lands lower (~185). Chunk boundaries don't matter to the panel — it concatenates. Writes with response.
- PNG payload must be genuinely deflate-compressed. Dart `image`/`archive` packages use real zlib — fine. (The ESP32 needed a hand-rolled encoder; Flutter does not.)
- **Rate limit**: full-frame `send_image` cannot sustain intervals < ~320 ms. Sprite scrolling at ~120 ms works because frames are small crops. Any animation loop must respect this.
- **Disconnect guard**: after 2 consecutive timeout/no-ack failures, disconnect and surface a non-modal error (status-bar style, never a dialog per failure; coalesce identical errors within 1 s).
- `send_text` (native panel text) dims backgrounds on some firmware — the app renders text as images via sprite fonts and `send_image` instead. Keep that architecture.
- **Brightness command bytes are NOT in the C++ reference.** They must be read from the `pypixelcolor` Python sources installed in S1. Do not guess them.

### Rendering facts

- Canvas 64×16 RGB. Sprite fonts are PNG sheets sliced by `cols` into fixed-width tiles, mapped by `order` string.
- `TEXT_GLYPH_ORDER = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$% '`
- `CLOCK_GLYPH_ORDER = '0123456789:'`
- Sprite font library entries: `{name, path, order, cols}`. Bundled sheets in `Gallery/Sprites/*.png`.
- ~~Non-black pixels in a glyph are recolored to the chosen text color~~ **CORRECTED during S3 (2026-07-22)**: the sprite pipeline does NO recoloring — glyphs are alpha-composited with their baked-in sheet colors onto a solid `bg_color` fill (`sprite_font.py:255,267`; `sprite_sender.py` passes no text color). `text_color` is consumed ONLY by the non-sprite `send_text` fallback (`qt/pages/text_page.py:203`). S7 must NOT add glyph recoloring to the sprite path.

### Persistence facts

- Legacy files: `ipixel_settings.json` (UI prefs, last device, sprite-font library under key `sprite_fonts`), `ipixel_presets.json` (list of preset dicts, each with a `type` key matching a feature id), `ipixel_secrets.json` (API keys, never committed), `playlists/*.json` (`{"name", "items":[{"preset_name","duration"}]}`).
- `ipixel_presets.json` is committed at repo root — use it as an import fixture. Settings/secrets are gitignored; use these synthetic fixtures for their shapes:
  - settings: `{"last_device": "AA:BB:CC:DD:EE:FF", "sprite_fonts": [{"name": "Text Thin", "path": "Gallery/Sprites/Text-thin-Sprite.png", "order": "0123…", "cols": 10}]}`
  - secrets: `{"youtube_api_key": "REDACTED", "weather_api_key": "REDACTED", "ig_user_id": "REDACTED", "ig_access_token": "REDACTED"}`
- The Flutter app stores its files in the platform app-support dir (`path_provider`), NOT the working directory, but must be able to IMPORT the three JSON files from the old app.

## Dependency graph

```
S1 scaffold ──┬── S2 protocol core   (‖ with S3, S5)
              ├── S3 render core     (‖ with S2, S5)
              └── S5 config layer    (‖ with S2, S3)
S2 ──────────── S4 BLE transport (incl. macOS entitlements)
S4 ──────────── S6 app shell (binds S4 providers)
S2,S3,S4,S6 ─── S7 text page + sprite sender + Android perms  ← end-to-end milestone
S4,S6 ───────── S8 image page   (‖ with S9; isolate route registration)
S7 ──────────── S9 clock page   (‖ with S8)
S5,S7,S8,S9 ─── S10 presets + home + reconnect-on-launch
S10 ─────────── S11 iOS enablement + Windows/Linux BLE proof
S11 ─────────── S12 CI release builds + icons + docs
```

Parallel groups: {S2, S3, S5} after S1; {S8, S9} after S7 (each registers its route in its own file — see S8/S9).

---

## Step 1 — Toolchain + project scaffold + protocol reference

**Model**: default. **Branch**: `flutter/scaffold`.

Install Flutter (stable channel) on macOS via `brew install --cask flutter`; run `flutter doctor` and resolve macOS/iOS/Android toolchain items (Android Studio / cmdline-tools needed for Android). Then:

1. `flutter create flutter_app --org com.frsname --project-name ipixel_controller --platforms=windows,macos,linux,ios,android` at repo root.
2. Add deps to `pubspec.yaml`: `universal_ble`, `image`, `path_provider`, `flutter_riverpod`. CRC32 comes from `archive`'s `getCrc32` (transitive dep of `image`) or a ~15-line implementation.
3. **Vendor the protocol reference**: `pip install pypixelcolor` into a local venv on this Mac and confirm the sources are readable (`python -c "import pypixelcolor, inspect; print(inspect.getfile(pypixelcolor))"`). S2 needs them for the brightness byte layout and golden vectors. Record the resolved path in this plan's mutation log.
4. Copy `Gallery/Sprites/*.png` into `flutter_app/assets/sprites/` and register in pubspec. Note in code where the canonical copies live.
5. `analysis_options.yaml`: `flutter_lints` defaults.
6. GitHub Actions workflow `.github/workflows/flutter.yml`: on PR touching `flutter_app/**` → `flutter analyze` + `flutter test` on ubuntu; build jobs added in S12.
7. App builds and shows a placeholder screen on macOS (`flutter run -d macos`).

**Exit criteria**: `flutter analyze` clean, `flutter test` passes (default smoke test), macOS app launches, CI green on PR, pypixelcolor sources readable locally.
**Rollback**: delete `flutter_app/` + workflow file; no existing code touched.

## Step 2 — Protocol core (pure Dart, no BLE)

**Model**: strongest. **Branch**: `flutter/protocol-core`. **Depends**: S1. **Parallel with**: S3, S5.

Create `flutter_app/lib/protocol/`:

- `crc32.dart` — standard CRC-32 (IEEE, reflected, poly 0xEDB88320). Verify against `zlib.crc32(b"123456789") == 0xCBF43926`.
- `frames.dart` — pure functions: `buildHandshake(DateTime now)`, `buildSendImageFrames(Uint8List png, {int slot = 0, required int chunkSize})` returning framed payload split into chunks, `buildBrightness(int pct)` (byte layout from the pypixelcolor sources installed in S1 — NOT in the C++ reference), `buildPower(bool on)` (`[5,0,7,1,on?1:0]`, cpp ~220).
- `ack.dart` — notify-frame classifier: any-frame signal vs final-ack (`len >= 5 && data[0]==0x05 && data[4]==0x03`).

**Tests** (`test/protocol/`): golden byte vectors generated ONCE with the S1 pypixelcolor install (`python -c` snippets), hard-coded with a provenance comment. Cover: prefix arithmetic (`15 + pngLen`), CRC endianness (LE in frame), chunk boundaries at 244 AND at a sub-244 size (e.g. 182 for MTU 185), handshake time bytes, brightness, power.

**Exit criteria**: 100% of frame-builder branches covered by golden tests; `flutter test` green.
**Rollback**: revert PR; nothing depends on it yet.

## Step 3 — Render core (pure Dart)

**Model**: default. **Branch**: `flutter/render-core`. **Depends**: S1. **Parallel with**: S2, S5.

Create `flutter_app/lib/render/` using the `image` package (NOT `dart:ui` — must run in pure Dart tests and isolates):

- `sprite_font.dart` — port of `SpriteFont`: load sheet from asset/file, slice by `cols`, glyph lookup by `order`, expose `tileWidth/tileHeight`. Port `SpriteFontService`: registry, `renderTextLine`, `renderTextFixed(w=64,h=16)` with text/bg color substitution (non-black glyph pixels → textColor).
- `panel_image.dart` — 64×16 canvas ops: fit/center arbitrary images (for S8), fill bg, composite, encode to PNG (`encodePng`).
- Port `speed_to_interval_ms`.

**Tests**: load a real bundled sprite sheet, render "12:34" and a short string, assert canvas size, glyph pixel colors at known coordinates, PNG round-trip decode.

**Exit criteria**: golden parity with Python — generate one reference PNG with the Python `SpriteFontService`, commit to `test/fixtures/`, then **decode both PNGs and compare RGB pixel arrays** (PNG bytes differ between encoders — never byte-compare). Choose a reference string short enough to fit 64×16 WITHOUT triggering the resize path in `sprite_font.py` (~lines 318–328), so resampling differences can't cause false failures.
**Rollback**: revert PR.

## Step 4 — BLE transport (universal_ble) + macOS enablement

**Model**: strongest. **Branch**: `flutter/ble-transport`. **Depends**: S2.

Create `flutter_app/lib/ble/`:

- `transport.dart` — thin `BleTransport` interface (scan stream, connect, discover, write-with-response, notify stream, mtu). `universal_ble_transport.dart` implements it. Feature code never imports `universal_ble` directly.
- `scanner.dart` — scan filtered by the name patterns in the global brief; expose stream of `(name, id, rssi)` sorted by RSSI.
- `device_session.dart` — connect flow: connect → negotiate MTU (`requestMtu(247)` on Android; read negotiated value elsewhere) → discover → resolve fa02/fa03 → subscribe notify → **send handshake** → mark ready. Serialized command queue (single in-flight operation — fixes the Python app's thread-per-send race). `sendImage(Uint8List png)` chunks at `min(244, mtu-3)`, awaits final-ack with timeout. `setBrightness`, `setPower`.
- `session_guard.dart` — 2-consecutive-failure disconnect rule + error coalescing (identical error strings within 1 s emit once).
- Riverpod providers: `connectionState`, `lastError`, `lastDeviceId` (persisted; on macOS/iOS the id is a CoreBluetooth UUID, not a MAC — never assume MAC format).
- **macOS enablement in this step** (required for the exit criterion): `com.apple.security.device.bluetooth` in BOTH `DebugProfile.entitlements` and `Release.entitlements`, `NSBluetoothAlwaysUsageDescription` in Info.plist.

**Verification**: manual against a real panel from macOS (`flutter run -d macos`): scan finds panel, connect + handshake succeeds, a hard-coded 64×16 test PNG renders on the panel. Log notify frames and compare with CLAUDE.md's documented ack bytes. Unit-test queue/guard/MTU-chunking logic against a fake `BleTransport`.

**Exit criteria**: test image visibly renders on physical panel from macOS; queue/guard unit tests green. (If no panel is at hand, the step may merge on unit tests + a mutation-log note, but S7 CANNOT start until panel verification happens.)
**Rollback**: revert PR.

## Step 5 — Config/persistence layer

**Model**: default. **Branch**: `flutter/config-layer`. **Depends**: S1. **Parallel with**: S2, S3, S4.

Create `flutter_app/lib/config/`:

- `config_store.dart` — JSON files in `path_provider` app-support dir: `settings.json`, `presets.json`, `secrets.json`. Same key names as the Python app where sensible. Atomic writes (write temp + rename).
- `models.dart` — typed `Preset` (with `type` discriminator), `SpriteFontEntry {name, path, order, cols}`, `Playlist`.
- `import_legacy.dart` — file-picker import of the old app's three JSON files; map sprite-font paths: bundled ones remap to Flutter assets, user ones copy into app-support.
- Seed defaults: bundled sprite fonts registered on first launch (mirror `_ensure_default_sprite_fonts`).

**Tests**: round-trip save/load; legacy import against (a) a fixture copy of the repo's committed `ipixel_presets.json`, (b) the synthetic settings/secrets fixtures from the global brief (real ones are gitignored — do not hunt for them).

**Exit criteria**: tests green; imported fixture presets produce valid typed presets.
**Rollback**: revert PR.

## Step 6 — App shell + UI foundation

**Model**: default. **Branch**: `flutter/app-shell`. **Depends**: S4 (binds its providers), S1.

Create `flutter_app/lib/ui/`:

- Responsive shell: `NavigationRail` (desktop/tablet wide) ⇄ `NavigationBar` (phone). Pages: Home, Text, Image, Clock, Settings (placeholders where the feature isn't built yet). Route/page registration: one file per page registers itself (see S8/S9 parallelism note).
- Connection bar: scan/connect/disconnect UI bound to S4 providers; status + coalesced error display (non-modal — SnackBar/status strip, never dialogs).
- Panel preview widget: current 64×16 frame upscaled nearest-neighbor (`FilterQuality.none`) — UX upgrade over the Python app: every page previews before sending.
- Theme: dark, follow the Qt app's look loosely; no pixel parity.

**Exit criteria**: on macOS — navigation + live connection status against the real S4 providers. On iOS simulator — navigation only (BLE does not exist in the simulator; do not gate on it). `flutter analyze` clean.
**Rollback**: revert PR.

## Step 7 — Text feature + sprite sender + Android enablement (END-TO-END MILESTONE)

**Model**: default. **Branch**: `flutter/text-page`. **Depends**: S2, S3, S4 (panel-verified), S6.

- `lib/features/text/` — text input, color pickers (text/bg), sprite-font dropdown, static vs scroll mode, speed slider.
- `sprite_sender.dart` (shared service, port of `qt/sprite_sender.py`): render full text strip → scroll = crop 64×16 windows on a periodic timer (~120 ms floor); static = single send. Exactly one active display task app-wide: an `ActiveDisplayTask` slot in a provider — assigning a new task disposes the old one (structural version of `_stop_active_display_tasks`).
- **Android enablement in this step** (required for the exit criterion): `BLUETOOTH_SCAN`/`BLUETOOTH_CONNECT` (API 31+), legacy `BLUETOOTH`/`ACCESS_FINE_LOCATION` for API ≤ 30, runtime permission flow with rationale UI.
- Live panel-preview wired to the same rendered frames.

**Verification**: real panel — static text with white bg renders bright; scrolling runs ≥ 60 s without tripping the disconnect guard.

**Exit criteria**: physical-panel verification on macOS AND one Android device; preview matches panel output.
**Rollback**: revert PR; S6 placeholders remain.

## Step 8 — Image feature

**Model**: default. **Branch**: `flutter/image-page`. **Depends**: S4, S6 (+ S3 helpers). **Parallel with**: S9 — each page registers its route in its own file; neither edits a shared registration file (pre-created stubs from S6 avoid merge conflicts).

- Pick image (`file_selector` desktop / `image_picker` mobile), letterbox-or-crop choice to 64×16, preview, send. GIFs: decode frames, play as timed loop respecting the ≥320 ms full-frame floor, through the `ActiveDisplayTask` slot.

**Exit criteria**: PNG and GIF verified on panel.
**Rollback**: revert PR.

## Step 9 — Clock feature

**Model**: default. **Branch**: `flutter/clock-page`. **Depends**: S7. **Parallel with**: S8 (same route-isolation rule).

- Modes: sprite-clock (CLOCK_GLYPH_ORDER fonts, e.g. `BiggerClocksSprite.png`), custom format via text pipeline, countdown.
- Tick per minute (per second only when format shows seconds) through the `ActiveDisplayTask` slot; **send only when the rendered string OR colors change** (ESP32 lesson: compare rendered output, not the time).

**Exit criteria**: clock updates on panel across a minute boundary; countdown reaches zero state correctly.
**Rollback**: revert PR.

## Step 10 — Presets + Home + reconnect-on-launch

**Model**: default. **Branch**: `flutter/presets`. **Depends**: S5, S7, S8, S9.

- Save-as-preset on each feature page; `Preset.type` dispatches execution to the owning feature (registry, mirror of `MainWindow._run_preset` → `execute_preset`).
- Home: preset tiles, brightness slider + power toggle (S2 frames).
- **Reconnect-on-launch**: on startup, if `lastDeviceId` is set, attempt connect with a visible cancel affordance (parity with the ESP32's auto-reconnect; the Python app lacks this).
- Legacy-import button in Settings.

**Exit criteria**: save → restart app → run preset works for text/image/clock; auto-reconnect connects to the panel on launch; imported legacy presets execute.
**Rollback**: revert PR.

## Step 11 — iOS enablement + Windows/Linux BLE proof

**Model**: default. **Branch**: `flutter/platform-enablement`. **Depends**: S10.

- **iOS**: `NSBluetoothAlwaysUsageDescription` in Info.plist; verify on a physical iPhone (BLE never works in the simulator). Free provisioning suffices for personal sideloading (7-day re-sign).
- **Windows**: build on the user's Windows machine (`flutter build windows` or `flutter run -d windows`); verify universal_ble scan → connect → text send against the panel. If universal_ble fails here, swap the Windows backend behind `BleTransport` (e.g. `win_ble`) — interface exists for exactly this.
- **Linux**: verify universal_ble's BlueZ path (VM or spare machine); document `bluez` prerequisites. Same backend-swap escape hatch.

**Exit criteria**: text feature verified on physical iPhone AND Windows; Linux verified or explicitly deferred with a mutation-log entry.
**Rollback**: revert PR.

## Step 12 — CI release builds, icons, docs

**Model**: default. **Branch**: `flutter/release-ci`. **Depends**: S11.

- App icons for all platforms (`flutter_launcher_icons`; the ECC `ios-icon-gen` skill can generate the iOS set).
- Extend CI: `windows-latest` job → `flutter build windows` → zip artifact on tag; `macos-latest` job likewise. Android APK on tag.
- README section for the Flutter app; note the Python app's status (unchanged, still the Windows daily driver until parity).

**Exit criteria**: tagging a release produces Windows zip + macOS zip + Android APK artifacts; user validates the Windows artifact on their machine.
**Rollback**: revert PR.

---

## Backlog (post-core, not planned in detail yet)

Stock (call Yahoo Finance JSON endpoints directly — no yfinance in Dart), Weather (OpenWeatherMap), YouTube (Data API v3), Instagram (Graph API + token refresh), procedural animations (Game of Life / Matrix / Fire / Starfield / Plasma — respect 320 ms floor or pre-render as scroll-crops), playlists, Draw page (webview or native editor), sprite-font library management UI.

## Invariants (verify after every step)

1. `flutter analyze` clean, `flutter test` green.
2. No step modifies `ipixel_controller*`, `esp32-firmware/`, or the Python app's runtime files.
3. Everything sent to the panel goes through the S4 session queue — no direct characteristic writes from features; no feature imports `universal_ble` directly.
4. One active display task at a time, owned by the `ActiveDisplayTask` slot.
5. No secrets in git (`secrets.json` lives only in app-support dir).

## Plan mutation log

- 2026-07-23 — S6 executed and merged (unit tests + macOS debug build; PANEL VERIFICATION PENDING from S4 unchanged, S7 gate unchanged). Page registry: one `PageDef` per page file, self-registering, with S8/S9 stubs (`image_page.dart`, `clock_page.dart`) pre-created so parallel branches never touch `page_registry.dart`. Shell body is an `IndexedStack` — pages are built once and kept alive, so S7-S9 feature pages may rely on local state persisting across tab switches. `panelScannerProvider` added to `lib/ble/providers.dart`: wiring of the existing S4 `PanelScanner` for the connection bar, not a new transport API. Last-device-id persistence in the connect path is fire-and-forget (`ConfigStore` serializes writes in call order, so ordering is preserved without awaiting). flutter_riverpod 3.3.2 has no `AsyncValue.valueOrNull` — use `.value` instead. Review hardening round: Exception-only error mapping to friendly copy, double-tap connect guard, `Semantics` label on the status indicator, defensive scan stop in `dispose`.
- 2026-07-22 — S4 executed and merged on unit tests via the escape hatch: **PANEL VERIFICATION PENDING — S7 must not start until a physical panel verifies scan→connect→handshake→send_image from macOS.** The probe (`flutter run -d macos -t lib/ble/probe_main.dart`) launched cleanly but blocked on the interactive macOS Bluetooth permission dialog (entitlements verified correct; no TCC abort) — needs a human to answer the prompt with a powered-on panel nearby. universal_ble 2.1.0 API adaptation: `requestMtu` is a unified request/query call (Android requests, Apple/Windows/Linux return the OS-negotiated value); name-substring filtering done in Dart (ScanFilter only supports prefixes). Review hardening (3 rounds): disconnect serialized vs command queue via local session snapshots, connect reentrancy guard + phase timeouts (30s/10s), race-free statusChanges seeding (onListen subscribe→seed→flush), coalesce window anchored to first-of-run, teardown-vs-guard misattribution fixed. LOW follow-up for a later step: wrap `transport.disconnect()` in a timeout or check `_deviceId == null` in the reclassification path (narrow misattribution window if a platform disconnect hangs).
- 2026-07-22 — S2/S3 findings. S2: brightness = `[5,0,4,0x80,level]` (pyref `commands/set_brightness.py:12-18`); golden vectors EXECUTED against pypixelcolor via python3.13 venv; `buildSendImageFrames` enforces pyref's 12288-byte single-window limit (`send_image.py:335`, `send_plan.py:19`). S3: rendering-facts bullet about glyph recoloring was WRONG and is corrected above — sprite path composites baked-in glyph colors, no text-color tint; Dart port verified pixel-identical to Python (0/1024 diff, fixture `test/fixtures/golden_clock_1234.png`).
- 2026-07-22 — S1 executed. Flutter 3.44.7 / Dart 3.12.2 installed via brew. pypixelcolor reference sources vendored at `flutter_app/tool/pyref/.venv/lib/python3.9/site-packages/pypixelcolor/` (gitignored). NOTE for S2: sources are readable but NOT executable under system Python 3.9 (package uses 3.10+ union syntax); golden-vector generation in S2 needs a Python ≥3.10 interpreter or must derive vectors by reading the source. CocoaPods 1.17.0 installed (needed for native plugin pods). Android SDK not yet configured — deferred to S7 as planned. CI hardening applied post-review: flutter-action cache+version pin, `dart format` check, `flutter analyze --fatal-infos`.
- 2026-07-21 — v2 after adversarial review (Opus). CRITICAL: replaced flutter_blue_plus with universal_ble behind a `BleTransport` interface (flutter_blue_plus has no Windows/Linux support). HIGH: moved macOS entitlements into S4, Android permissions into S7 (were blocking their own steps' hardware verification from S11); added S1 task to pip-install pypixelcolor (brightness bytes absent from C++ reference, sources absent from macOS box); split old S11 into S11 (platform enablement/proof) + S12 (CI release + icons + docs). MEDIUM: MTU-adaptive chunking `min(244, mtu-3)` + sub-244 golden test; reconnect-on-launch added to S10; S3 golden compares decoded pixels not PNG bytes, reference string must avoid the resize path; S6 now depends on S4 and its simulator check is navigation-only; synthetic settings/secrets fixtures documented (real files gitignored); S8/S9 route registration isolated. LOW: final-ack `len>=5`; scan filters extended with `LED-BLE-` / `BK Light`.
