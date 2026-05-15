#pragma once
#include <Arduino.h>
#include <vector>

struct BleScanDevice {
    String  name;
    String  mac;
    int8_t  rssi;
};

// Initialise the NimBLE stack and remember which panel MAC to try connecting
// to. Pass an empty string to leave the panel unset (Tick will not attempt
// any connections until ipixelBleSetPinnedMac() supplies one).
void ipixelBleSetup(const String& pinnedMac);

// Called from the main loop to drive reconnects (rate-limited internally).
void ipixelBleTick();

// True only when the GATT client has both write + notify characteristics
// resolved and the link is up.
bool ipixelBleIsConnected();

// Human-readable status string for the web UI ("connected" / "scanning…" /
// "no panel set" / "disconnected").
String ipixelBleStatusText();

// Update the pinned MAC. Triggers a fresh connect on the next tick.
void ipixelBleSetPinnedMac(const String& mac);

// Begin a non-blocking BLE scan. Results accumulate in the scan results
// buffer; poll via ipixelBleIsScanning() / ipixelBleScanResults(). Only
// devices whose advertised name matches the iPixel families are reported.
void ipixelBleScanStart(uint32_t durationSec = 5);
bool ipixelBleIsScanning();
std::vector<BleScanDevice> ipixelBleScanResults();

// Send a 64x16 RGB framebuffer as a single-window send_image PNG over the
// pypixelcolor protocol. Blocks for one round-trip (write + ack), typically
// well under a second on a healthy link.
bool ipixelBleSendFrame(const uint8_t* fb);
