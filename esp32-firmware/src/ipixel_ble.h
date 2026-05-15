#pragma once
#include <Arduino.h>

// Connect to the first iPixel-compatible panel discovered (or a specific
// MAC if `pinnedMac` is non-empty, format "aa:bb:cc:dd:ee:ff").
bool ipixelBleConnect(const String& pinnedMac);
void ipixelBleDisconnect();
bool ipixelBleIsConnected();

// Send a 64x16 RGB framebuffer to the panel, framed as the pypixelcolor
// `send_image` protocol expects (PNG-encoded internally, with CRC32 + length
// prefix, sliced into 12 KB windows).
//
// NOTE: PNG encoding + BLE chunking + ack handling are stubbed for the first
// milestone. See the .cpp for the protocol reference once you wire it up.
bool ipixelBleSendFrame(const uint8_t* fb /* PANEL_W*PANEL_H*3 */);
