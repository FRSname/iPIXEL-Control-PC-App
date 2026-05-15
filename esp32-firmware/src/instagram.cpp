#include "instagram.h"
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

// We skip cert validation for simplicity. Facebook rotates its CA; pinning
// it from firmware means a future rotation bricks the device. For a personal
// project on a trusted home network this is fine. If you want strict TLS,
// fetch the current `DigiCert Global Root CA` PEM and pass it to setCACert().
static const char* HOST = "graph.facebook.com";

IgResult igFetchFollowers(const String& igUserId, const String& token) {
    IgResult r{};
    if (igUserId.isEmpty() || token.isEmpty()) {
        r.error = "missing id or token";
        return r;
    }

    WiFiClientSecure client;
    client.setInsecure();
    client.setTimeout(10000);

    HTTPClient http;
    String url = String("https://") + HOST + "/v21.0/" + igUserId +
                 "?fields=followers_count,username&access_token=" + token;

    if (!http.begin(client, url)) {
        r.error = "http.begin failed";
        return r;
    }

    int code = http.GET();
    String body = http.getString();
    http.end();

    if (code != 200) {
        r.error = "HTTP " + String(code) + ": " + body.substring(0, 120);
        return r;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        r.error = String("JSON: ") + err.c_str();
        return r;
    }
    if (!doc["followers_count"].is<uint32_t>()) {
        r.error = "no followers_count in response";
        return r;
    }
    r.ok            = true;
    r.followerCount = doc["followers_count"].as<uint32_t>();
    r.username      = doc["username"].as<String>();
    return r;
}
