#pragma once
#include <Arduino.h>

// Persistent settings backed by ESP32 NVS (Preferences).
// All strings are kept short to fit the NVS 4000-byte budget comfortably.
struct AppConfig {
    String igUserId;        // "17841..." numeric Instagram Business Account ID
    String accessToken;     // Long-lived or System User token
    uint32_t refreshSec;    // Poll interval in seconds (min 60)
    uint8_t  formatMode;    // 0=count_short, 1=count_full, 2=username_count, 3=followers_label
    uint32_t textColor;     // 0xRRGGBB
    uint32_t bgColor;       // 0xRRGGBB
    String   panelMac;      // Optional: pin to a specific panel MAC; empty = scan-and-pick
    bool     rotate180;     // Mirror the framebuffer 180° before sending (panel mounted upside-down)
};

void configLoad(AppConfig& out);
void configSave(const AppConfig& in);
bool configIsProvisioned(const AppConfig& c);
