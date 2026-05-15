#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include "config.h"
#include "web_ui.h"
#include "instagram.h"
#include "renderer.h"
#include "ipixel_ble.h"

static AppConfig cfg;
static uint8_t   fb[FB_BYTES];

static uint32_t lastFollowerCount = 0;
static String   lastDisplayText;
static uint32_t lastFetchMs = 0;
static const uint32_t TWEEN_MS = 600;
static const uint32_t TWEEN_FRAME_MS = 33; // ~30 fps

// Mirror the IG service's _format_large_number() so display semantics match
// the desktop app (see ipixel_controller/services/instagram_service.py).
static String formatShort(uint32_t n) {
    char buf[16];
    if (n >= 1000000000UL)  snprintf(buf, sizeof(buf), "%.1fB", n / 1e9);
    else if (n >= 1000000U) snprintf(buf, sizeof(buf), "%.1fM", n / 1e6);
    else if (n >= 10000U)   snprintf(buf, sizeof(buf), "%luK", (unsigned long)(n / 1000));
    else if (n >= 1000U)    snprintf(buf, sizeof(buf), "%.1fK", n / 1000.0);
    else                    snprintf(buf, sizeof(buf), "%lu", (unsigned long)n);
    return String(buf);
}

static String formatForDisplay(uint32_t count, const String& username, uint8_t mode) {
    String s_short = formatShort(count);
    switch (mode) {
        case 1: return String(count);
        case 2: {
            String handle = "@" + (username.length() ? username : String("ig"));
            return handle + " " + s_short;
        }
        case 3: return "FOLLOWERS " + s_short;
        default: return s_short;
    }
}

static void pushFrame() {
    // Best-effort: log status whether or not BLE is wired up yet.
    if (ipixelBleIsConnected()) {
        ipixelBleSendFrame(fb);
    } else {
        // Once milestone 2 lands this will already be a no-op when connected.
        // For now, dump the first row's pixel count so we can sanity-check the renderer.
        int lit = 0;
        for (int x = 0; x < PANEL_W; ++x) {
            int y = (PANEL_H - 7) / 2 + 3; // middle row of glyph
            uint8_t* p = fb + (y * PANEL_W + x) * 3;
            if (p[0] || p[1] || p[2]) lit++;
        }
        Serial.printf("[render] mid-row lit pixels: %d / 64\n", lit);
    }
}

static void animateTo(const String& newText) {
    if (lastDisplayText.length() == 0) {
        rendererStaticFrame(fb, newText.c_str(), cfg.textColor, cfg.bgColor);
        pushFrame();
        lastDisplayText = newText;
        return;
    }
    uint32_t start = millis();
    while (true) {
        float t = (millis() - start) / (float)TWEEN_MS;
        if (t >= 1.0f) break;
        rendererTweenFrame(fb, lastDisplayText.c_str(), newText.c_str(),
                           cfg.textColor, cfg.bgColor, t);
        pushFrame();
        delay(TWEEN_FRAME_MS);
    }
    rendererStaticFrame(fb, newText.c_str(), cfg.textColor, cfg.bgColor);
    pushFrame();
    lastDisplayText = newText;
}

static void fetchAndDisplay() {
    Serial.println("[ig] fetching…");
    IgResult r = igFetchFollowers(cfg.igUserId, cfg.accessToken);
    if (!r.ok) {
        Serial.printf("[ig] error: %s\n", r.error.c_str());
        webUiSetStatus("", lastFollowerCount, r.error);
        return;
    }
    Serial.printf("[ig] @%s — %u followers\n", r.username.c_str(), r.followerCount);
    webUiSetStatus(r.username, r.followerCount, "");

    if (r.followerCount != lastFollowerCount) {
        String newText = formatForDisplay(r.followerCount, r.username, cfg.formatMode);
        animateTo(newText);
        lastFollowerCount = r.followerCount;
    }
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\n=== iPixel IG Counter ===");

    configLoad(cfg);

    WiFiManager wm;
    wm.setConfigPortalTimeout(180);
    if (!wm.autoConnect("iPixel-Setup")) {
        Serial.println("[wifi] portal timed out — rebooting");
        ESP.restart();
    }
    Serial.printf("[wifi] connected, IP=%s\n", WiFi.localIP().toString().c_str());

    webUiBegin(cfg);

    if (!configIsProvisioned(cfg)) {
        Serial.println("[ig] no token configured — open the web UI to set one");
    }

    // BLE setup is best-effort; the firmware keeps running even if the panel
    // is off. Reconnect cadence lives in ipixelBleTick() called from loop().
    ipixelBleSetup(cfg.panelMac);

    lastFetchMs = millis() - cfg.refreshSec * 1000UL; // force first fetch immediately
}

extern volatile bool gFetchNow;
extern volatile bool gWifiReset;

void loop() {
    if (gWifiReset) {
        Serial.println("[wifi] forgetting saved credentials, rebooting…");
        WiFi.disconnect(true, true);   // erase config + disconnect
        WiFiManager().resetSettings(); // clears WiFiManager's NVS slot too
        delay(300);
        ESP.restart();
    }

    ipixelBleTick();

    // When BLE comes up (or comes back after a drop) repaint whatever the
    // renderer last produced — otherwise the panel keeps showing its idle
    // screen until the follower count actually changes.
    static bool wasBleConnected = false;
    bool nowBle = ipixelBleIsConnected();
    if (nowBle && !wasBleConnected && lastDisplayText.length() > 0) {
        Serial.println("[ble] link up — repushing last frame");
        rendererStaticFrame(fb, lastDisplayText.c_str(), cfg.textColor, cfg.bgColor);
        ipixelBleSendFrame(fb);
    }
    wasBleConnected = nowBle;

    if (configIsProvisioned(cfg) &&
        (gFetchNow || (millis() - lastFetchMs) >= cfg.refreshSec * 1000UL)) {
        gFetchNow = false;
        lastFetchMs = millis();
        fetchAndDisplay();
    }
    delay(50);
}
