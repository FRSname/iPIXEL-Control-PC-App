#include "web_ui.h"
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <ArduinoJson.h>

static AsyncWebServer server(80);
static AppConfig* gCfg = nullptr;

static String   sUsername;
static uint32_t sCount = 0;
static String   sLastError;

// Set from the save handler so main's loop polls Instagram immediately rather
// than waiting for the next refresh tick.
volatile bool gFetchNow = false;

static String hexColor(uint32_t c) {
    char buf[8];
    snprintf(buf, sizeof(buf), "#%06lX", (unsigned long)(c & 0xFFFFFF));
    return String(buf);
}

static uint32_t parseHexColor(const String& s, uint32_t fallback) {
    String t = s;
    t.trim();
    if (t.startsWith("#")) t.remove(0, 1);
    if (t.length() != 6) return fallback;
    char* end = nullptr;
    uint32_t v = strtoul(t.c_str(), &end, 16);
    return (end && *end == 0) ? v : fallback;
}

void webUiSetStatus(const String& username, uint32_t count, const String& err) {
    sUsername = username;
    sCount    = count;
    sLastError = err;
}

void webUiBegin(AppConfig& cfgRef) {
    gCfg = &cfgRef;

    if (!LittleFS.begin(true)) {
        Serial.println("[web] LittleFS mount failed");
    }

    server.on("/", HTTP_GET, [](AsyncWebServerRequest* req) {
        if (LittleFS.exists("/index.html")) {
            req->send(LittleFS, "/index.html", "text/html");
        } else {
            req->send(200, "text/plain",
                "index.html missing on LittleFS. Run `pio run -t uploadfs`.");
        }
    });

    server.on("/api/config", HTTP_GET, [](AsyncWebServerRequest* req) {
        JsonDocument d;
        d["ig_user_id"]   = gCfg->igUserId;
        d["has_token"]    = gCfg->accessToken.length() > 0;
        d["refresh_sec"]  = gCfg->refreshSec;
        d["format_mode"]  = gCfg->formatMode;
        d["text_color"]   = hexColor(gCfg->textColor);
        d["bg_color"]     = hexColor(gCfg->bgColor);
        d["panel_mac"]    = gCfg->panelMac;
        String out;
        serializeJson(d, out);
        req->send(200, "application/json", out);
    });

    server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* req) {
        JsonDocument d;
        d["username"]   = sUsername;
        d["count"]      = sCount;
        d["last_error"] = sLastError;
        d["ip"]         = WiFi.localIP().toString();
        d["rssi"]       = WiFi.RSSI();
        String out;
        serializeJson(d, out);
        req->send(200, "application/json", out);
    });

    // POST form-encoded body to update config. Fields are optional; missing
    // ones keep their current value. Form-encoded data is parsed natively by
    // ESPAsyncWebServer into getParam(name, /*post=*/true), so we sidestep
    // the body-handler/request-handler ordering issues that come with JSON.
    server.on("/api/config", HTTP_POST, [](AsyncWebServerRequest* req) {
        auto get = [&](const char* k, String& out) {
            if (req->hasParam(k, true)) out = req->getParam(k, true)->value();
        };
        String s;
        get("ig_user_id", gCfg->igUserId);
        if (req->hasParam("access_token", true)) {
            String tok = req->getParam("access_token", true)->value();
            if (tok.length() > 0) gCfg->accessToken = tok;
        }
        if (req->hasParam("refresh_sec", true)) {
            uint32_t v = req->getParam("refresh_sec", true)->value().toInt();
            if (v >= 60) gCfg->refreshSec = v;
        }
        if (req->hasParam("format_mode", true)) {
            gCfg->formatMode = (uint8_t)req->getParam("format_mode", true)->value().toInt();
        }
        if (req->hasParam("text_color", true)) {
            gCfg->textColor = parseHexColor(req->getParam("text_color", true)->value(), gCfg->textColor);
        }
        if (req->hasParam("bg_color", true)) {
            gCfg->bgColor = parseHexColor(req->getParam("bg_color", true)->value(), gCfg->bgColor);
        }
        get("panel_mac", gCfg->panelMac);

        configSave(*gCfg);
        Serial.printf("[cfg] saved: ig_id=%s has_tok=%d refresh=%u fmt=%u\n",
                      gCfg->igUserId.c_str(),
                      (int)(gCfg->accessToken.length() > 0),
                      (unsigned)gCfg->refreshSec,
                      (unsigned)gCfg->formatMode);
        gFetchNow = true;
        req->send(200, "application/json", "{\"ok\":true}");
    });

    server.begin();
    Serial.printf("[web] http://%s/\n", WiFi.localIP().toString().c_str());
}
