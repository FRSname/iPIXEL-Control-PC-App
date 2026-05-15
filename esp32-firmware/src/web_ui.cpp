#include "web_ui.h"
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <ArduinoJson.h>

static AsyncWebServer server(80);
static AppConfig* gCfg = nullptr;

static String   sUsername;
static uint32_t sCount = 0;
static String   sLastError;

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

    // POST JSON body to update config. Fields are optional; missing ones keep
    // their current value. Token-only updates avoid leaking the token back via GET.
    //
    // We assemble the body manually rather than using AsyncCallbackJsonWebHandler
    // because that helper's header pulls in ArduinoJson 6 APIs that ArduinoJson 7
    // removed. The static buffer is fine for a personal-use config endpoint.
    server.on(
        "/api/config", HTTP_POST,
        [](AsyncWebServerRequest* /*req*/) {},
        nullptr,
        [](AsyncWebServerRequest* req, uint8_t* data, size_t len, size_t index, size_t total) {
            static String body;
            if (index == 0) body = "";
            body.concat((const char*)data, len);
            if (index + len < total) return;

            JsonDocument doc;
            if (deserializeJson(doc, body)) {
                req->send(400, "application/json", "{\"ok\":false,\"err\":\"bad json\"}");
                body = "";
                return;
            }
            JsonObject o = doc.as<JsonObject>();
            if (o["ig_user_id"].is<const char*>())   gCfg->igUserId    = o["ig_user_id"].as<const char*>();
            if (o["access_token"].is<const char*>()) gCfg->accessToken = o["access_token"].as<const char*>();
            if (o["refresh_sec"].is<uint32_t>())     gCfg->refreshSec  = o["refresh_sec"].as<uint32_t>();
            if (o["format_mode"].is<uint8_t>())      gCfg->formatMode  = o["format_mode"].as<uint8_t>();
            if (o["text_color"].is<const char*>())   gCfg->textColor   = parseHexColor(o["text_color"].as<const char*>(), gCfg->textColor);
            if (o["bg_color"].is<const char*>())     gCfg->bgColor     = parseHexColor(o["bg_color"].as<const char*>(), gCfg->bgColor);
            if (o["panel_mac"].is<const char*>())    gCfg->panelMac    = o["panel_mac"].as<const char*>();
            configSave(*gCfg);
            body = "";
            req->send(200, "application/json", "{\"ok\":true}");
        }
    );

    server.begin();
    Serial.printf("[web] http://%s/\n", WiFi.localIP().toString().c_str());
}
