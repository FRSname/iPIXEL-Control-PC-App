#include "ipixel_ble.h"

// =============================================================================
// MILESTONE 2 — TO IMPLEMENT
// =============================================================================
// This is a deliberate stub so you can flash + verify WiFi/web/IG fetch first.
// Once that part works, the BLE side gets implemented here using NimBLE-Arduino.
//
// Protocol reference (verified from installed pypixelcolor 0.4.0):
//
//   Service:        custom (discover by NOTIFY/WRITE UUIDs below)
//   WRITE char:     0000fa02-0000-1000-8000-00805f9b34fb
//   NOTIFY char:    0000fa03-0000-1000-8000-00805f9b34fb
//
//   send_image frame layout (per 12 KB window):
//     [2 LE: 2 + len(frame)]                            ← prefix
//     [0x02, 0x00, option]                              ← header (PNG)
//     [4 LE: total PNG size]
//     [4 LE: CRC32 of full PNG]
//     [0x00, save_slot]                                 ← tail
//     [chunk_payload]
//     option = 0x00 on first window, 0x02 on subsequent
//
//   Each window must wait for ACK on NOTIFY before sending the next.
//   See: pypixelcolor/commands/send_image.py and lib/transport/send_plan.py.
//
// Implementation outline:
//   1. NimBLEDevice::init("iPixel-Ctrl"); NimBLEScan::start(5s)
//      filter advertised name LIKE "LED_BLE_*" / "BGLight" / "B.K. Light"
//   2. On connect: discover service, get WRITE + NOTIFY characteristics,
//      subscribe to NOTIFY → ack queue.
//   3. PNG-encode the 64x16 RGB framebuffer (small — 1024 px ≈ <1 KB PNG).
//      Use a minimal PNG encoder (e.g. uPNG-encoder or bitbank2/PNGenc).
//   4. Build the framed message, split into 12 KB windows (one window fits
//      for a 64x16 PNG — we never hit the multi-window path for follower text).
//   5. Write in MTU-sized chunks (request 247-byte MTU on connect for speed),
//      wait for NOTIFY ack between windows.
// =============================================================================

bool ipixelBleConnect(const String& /*pinnedMac*/) {
    Serial.println("[ble] TODO: connect — milestone 2");
    return false;
}

void ipixelBleDisconnect() {}

bool ipixelBleIsConnected() { return false; }

bool ipixelBleSendFrame(const uint8_t* /*fb*/) {
    Serial.println("[ble] TODO: send_image — milestone 2");
    return false;
}
