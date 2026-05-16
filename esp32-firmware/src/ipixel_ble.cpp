#include "ipixel_ble.h"
#include "png_encode.h"
#include "renderer.h"        // for PANEL_W / PANEL_H / FB_BYTES
#include <NimBLEDevice.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

// pypixelcolor protocol UUIDs (see pypixelcolor/lib/constants.py).
static const NimBLEUUID WRITE_UUID ("0000fa02-0000-1000-8000-00805f9b34fb");
static const NimBLEUUID NOTIFY_UUID("0000fa03-0000-1000-8000-00805f9b34fb");

static String           g_pinnedMac;
static volatile bool    g_scanning      = false;
static SemaphoreHandle_t g_scanMutex    = nullptr;
static std::vector<BleScanDevice> g_scanResults;

static NimBLEClient*    g_client       = nullptr;
static NimBLERemoteCharacteristic* g_writeChar  = nullptr;
static NimBLERemoteCharacteristic* g_notifyChar = nullptr;

static SemaphoreHandle_t g_ackSem      = nullptr;
static volatile bool    g_ackFinal     = false;

static uint32_t         g_lastAttempt  = 0;
static bool             g_attemptedOnce = false;
static const uint32_t   RETRY_MS       = 10000;

static volatile bool    g_rotate180    = false;

// Panels advertise under one of several names depending on firmware vendor.
static bool nameLooksLikePanel(const String& name) {
    if (name.length() == 0) return false;
    if (name.startsWith("LED_BLE_") || name.startsWith("LED-BLE-")) return true;
    if (name.equalsIgnoreCase("BGLight")) return true;
    if (name.equalsIgnoreCase("B.K. Light")) return true;
    if (name.equalsIgnoreCase("BK Light"))   return true;
    return false;
}

class ScanCb : public NimBLEAdvertisedDeviceCallbacks {
    void onResult(NimBLEAdvertisedDevice* adv) override {
        String name = String(adv->getName().c_str());
        if (!nameLooksLikePanel(name)) return;
        String mac  = String(adv->getAddress().toString().c_str());
        int    rssi = adv->getRSSI();
        if (g_scanMutex) xSemaphoreTake(g_scanMutex, portMAX_DELAY);
        bool found = false;
        for (auto& d : g_scanResults) {
            if (d.mac.equalsIgnoreCase(mac)) {
                d.name = name; d.rssi = (int8_t)rssi; found = true; break;
            }
        }
        if (!found) g_scanResults.push_back({name, mac, (int8_t)rssi});
        if (g_scanMutex) xSemaphoreGive(g_scanMutex);
    }
};
static ScanCb g_scanCb;

static void scanEndedCb(NimBLEScanResults /*r*/) { g_scanning = false; }

// Fires for every NOTIFY frame. send_image ACKs are "0x05 _ _ _ code" with
// code 0/1 = window ack and code 3 = final ack (matches AckManager). Other
// frames (e.g. the 11-byte device-info reply from the handshake) use their
// own shape, so we wake the semaphore unconditionally and let the caller
// filter by inspecting g_ackFinal / drain stale acks before each send.
static void notifyHandler(NimBLERemoteCharacteristic* /*ch*/,
                          uint8_t* data, size_t len, bool /*isNotify*/) {
    char hex[64] = {0};
    size_t n = len < 16 ? len : 16;
    for (size_t i = 0; i < n; ++i) snprintf(hex + i * 3, sizeof(hex) - i * 3, "%02x ", data[i]);
    Serial.printf("[ble] notify len=%u: %s\n", (unsigned)len, hex);

    if (len >= 5 && data[0] == 0x05 && data[4] == 3) g_ackFinal = true;
    if (g_ackSem) xSemaphoreGive(g_ackSem);
}

class ClientCb : public NimBLEClientCallbacks {
    void onConnect(NimBLEClient* /*c*/) override {
        Serial.println("[ble] onConnect");
    }
    void onDisconnect(NimBLEClient* /*c*/) override {
        Serial.println("[ble] onDisconnect");
        g_writeChar  = nullptr;
        g_notifyChar = nullptr;
    }
    uint32_t onPassKeyRequest() override { return 0; }
};
static ClientCb g_clientCb;

void ipixelBleSetup(const String& pinnedMac) {
    g_pinnedMac = pinnedMac;
    if (!g_scanMutex) g_scanMutex = xSemaphoreCreateMutex();
    if (!g_ackSem)    g_ackSem    = xSemaphoreCreateBinary();

    NimBLEDevice::init("iPixel-Ctrl");
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);
    NimBLEDevice::setMTU(247);

    NimBLEScan* pScan = NimBLEDevice::getScan();
    pScan->setAdvertisedDeviceCallbacks(&g_scanCb, false);
    pScan->setActiveScan(true);
    pScan->setInterval(100);
    pScan->setWindow(99);

    Serial.println("[ble] NimBLE initialised");
}

void ipixelBleScanStart(uint32_t durationSec) {
    if (g_scanning) return;
    if (g_scanMutex) {
        xSemaphoreTake(g_scanMutex, portMAX_DELAY);
        g_scanResults.clear();
        xSemaphoreGive(g_scanMutex);
    }
    g_scanning = true;
    NimBLEScan* pScan = NimBLEDevice::getScan();
    if (!pScan->start(durationSec, scanEndedCb, false)) {
        // Already running or stack busy — clear flag so the user can retry.
        g_scanning = false;
        Serial.println("[ble] scan start refused");
    } else {
        Serial.printf("[ble] scan started (%us)\n", (unsigned)durationSec);
    }
}

bool ipixelBleIsScanning() { return g_scanning; }

std::vector<BleScanDevice> ipixelBleScanResults() {
    std::vector<BleScanDevice> copy;
    if (g_scanMutex) xSemaphoreTake(g_scanMutex, portMAX_DELAY);
    copy = g_scanResults;
    if (g_scanMutex) xSemaphoreGive(g_scanMutex);
    return copy;
}

void ipixelBleSetPinnedMac(const String& mac) {
    g_pinnedMac = mac;
    if (g_client && g_client->isConnected()) g_client->disconnect();
    g_lastAttempt = 0; // try immediately
}

bool ipixelBleIsConnected() {
    return g_client && g_client->isConnected() && g_writeChar && g_notifyChar;
}

String ipixelBleStatusText() {
    if (ipixelBleIsConnected()) return "connected";
    if (g_scanning)              return "scanning";
    if (g_pinnedMac.length() == 0) return "no panel set";
    return "disconnected";
}

static bool resolveChars() {
    std::vector<NimBLERemoteService*>* services = g_client->getServices(true);
    if (!services) return false;
    for (auto* svc : *services) {
        NimBLERemoteCharacteristic* wc = svc->getCharacteristic(WRITE_UUID);
        if (wc) g_writeChar = wc;
        NimBLERemoteCharacteristic* nc = svc->getCharacteristic(NOTIFY_UUID);
        if (nc) g_notifyChar = nc;
        if (g_writeChar && g_notifyChar) break;
    }
    return g_writeChar && g_notifyChar;
}

static bool tryConnect() {
    if (g_pinnedMac.length() == 0) return false;
    if (g_scanning) return false;

    if (!g_client) {
        g_client = NimBLEDevice::createClient();
        g_client->setClientCallbacks(&g_clientCb, false);
        g_client->setConnectTimeout(15);
    }

    Serial.printf("[ble] connecting to %s…\n", g_pinnedMac.c_str());
    NimBLEAddress addr(g_pinnedMac.c_str(), BLE_ADDR_PUBLIC);
    if (!g_client->connect(addr, true)) {
        Serial.println("[ble] connect failed");
        return false;
    }

    if (!resolveChars()) {
        Serial.println("[ble] required characteristics not found");
        g_client->disconnect();
        return false;
    }

    // Subscribe with write-response on the CCCD so we know the panel accepted
    // the notification request. Some firmware variants ignore write-without-
    // response CCCD updates and silently drop subsequent ACKs.
    if (!g_notifyChar->subscribe(true, notifyHandler, true)) {
        Serial.println("[ble] notify subscribe failed");
        g_client->disconnect();
        return false;
    }

    // Required handshake — pypixelcolor's DeviceSession.connect() always
    // sends this get_device_info command right after subscribing. Without it
    // the panel ACKs subsequent send_image frames but ignores their content.
    // Format: [8, 0, 1, 0x80, hour, minute, second, language=0]
    while (xSemaphoreTake(g_ackSem, 0) == pdTRUE) {}
    uint8_t initCmd[8] = { 8, 0, 1, 0x80, 0, 0, 0, 0 };
    if (!g_writeChar->writeValue(initCmd, sizeof(initCmd), true)) {
        Serial.println("[ble] init handshake write failed");
        g_client->disconnect();
        return false;
    }
    if (xSemaphoreTake(g_ackSem, pdMS_TO_TICKS(1500)) != pdTRUE) {
        Serial.println("[ble] init handshake: no response (continuing anyway)");
    } else {
        Serial.println("[ble] init handshake OK");
    }

    // Belt-and-braces: explicitly power the panel on. The desktop app exposes
    // this in the Settings page but doesn't call it automatically — including
    // it here is harmless if the panel is already on.
    // pypixelcolor set_power command: [5, 0, 7, 1, on?1:0]
    while (xSemaphoreTake(g_ackSem, 0) == pdTRUE) {}
    uint8_t powerCmd[5] = { 5, 0, 7, 1, 1 };
    if (g_writeChar->writeValue(powerCmd, sizeof(powerCmd), true)) {
        xSemaphoreTake(g_ackSem, pdMS_TO_TICKS(500));
        Serial.println("[ble] set_power(on) sent");
    }

    Serial.printf("[ble] connected (MTU=%u)\n", (unsigned)g_client->getMTU());
    return true;
}

void ipixelBleTick() {
    if (ipixelBleIsConnected()) return;
    if (g_scanning) return;
    if (g_pinnedMac.length() == 0) return;
    uint32_t now = millis();
    // First attempt fires immediately; subsequent attempts are rate-limited.
    if (g_attemptedOnce && (now - g_lastAttempt < RETRY_MS)) return;
    g_attemptedOnce = true;
    g_lastAttempt = now;
    tryConnect();
}

void ipixelBleSetRotate180(bool on) {
    g_rotate180 = on;
}

bool ipixelBleSendFrame(const uint8_t* fb) {
    if (!ipixelBleIsConnected()) return false;

    // If rotation is enabled, mirror the framebuffer in-place into a scratch
    // buffer: pixel (x,y) → (W-1-x, H-1-y). Keeps the renderer orientation-
    // agnostic so every code path (Instagram, tween frames, repush-on-reconnect)
    // picks up the rotation automatically.
    const uint8_t* src = fb;
    static uint8_t rotated[FB_BYTES];
    if (g_rotate180) {
        for (int y = 0; y < PANEL_H; ++y) {
            for (int x = 0; x < PANEL_W; ++x) {
                const uint8_t* s = fb + (y * PANEL_W + x) * 3;
                uint8_t* d = rotated + (((PANEL_H - 1 - y) * PANEL_W) + (PANEL_W - 1 - x)) * 3;
                d[0] = s[0]; d[1] = s[1]; d[2] = s[2];
            }
        }
        src = rotated;
    }

    static uint8_t png[3800];   // 64x16 PNG fits within ~3540 bytes (fixed-Huffman worst case)
    size_t pngLen = pngEncode64x16RGB(src, png, sizeof(png));
    if (pngLen == 0) {
        Serial.println("[ble] PNG encode failed");
        return false;
    }
    uint32_t pngCrc = crc32Std(png, pngLen);

    // Dump the first PNG we transmit so we can verify it decodes correctly on
    // a PC (paste the hex into `bytes.fromhex(...)`, then PIL/imagemagick).
    // Only fires once per boot — flips off after the first send.
    static bool s_dumpPng = true;
    if (s_dumpPng) {
        s_dumpPng = false;
        Serial.printf("[ble] PNG dump (%u bytes, CRC=0x%08x) BEGIN\n",
                      (unsigned)pngLen, (unsigned)pngCrc);
        for (size_t i = 0; i < pngLen; ++i) {
            Serial.printf("%02x", png[i]);
            if ((i & 31) == 31) Serial.println();
        }
        if (pngLen & 31) Serial.println();
        Serial.println("[ble] PNG dump END");
    }

    // Single window suffices: 64x16 fits well below the 12KB window limit.
    // Frame body = [0x02 0x00 option(3)] + [size(4)] + [crc(4)] + [0x00 slot(2)] + payload
    const size_t bodyLen = 3 + 4 + 4 + 2 + pngLen;
    static uint8_t frame[4000];
    if (bodyLen + 2 > sizeof(frame)) return false;

    uint16_t prefix = (uint16_t)(2 + bodyLen);
    frame[0] = (uint8_t)(prefix & 0xFF);
    frame[1] = (uint8_t)((prefix >> 8) & 0xFF);
    frame[2] = 0x02; frame[3] = 0x00;
    frame[4] = 0x00;                              // option=0 (first/only window, PNG)
    frame[5] = (uint8_t)(pngLen & 0xFF);
    frame[6] = (uint8_t)((pngLen >>  8) & 0xFF);
    frame[7] = (uint8_t)((pngLen >> 16) & 0xFF);
    frame[8] = (uint8_t)((pngLen >> 24) & 0xFF);
    frame[ 9] = (uint8_t)(pngCrc & 0xFF);
    frame[10] = (uint8_t)((pngCrc >>  8) & 0xFF);
    frame[11] = (uint8_t)((pngCrc >> 16) & 0xFF);
    frame[12] = (uint8_t)((pngCrc >> 24) & 0xFF);
    frame[13] = 0x00; frame[14] = 0x00;           // tail: 0x00, save_slot=0
    memcpy(frame + 15, png, pngLen);
    const size_t totalLen = 15 + pngLen;

    // Drain any stale notify events.
    while (xSemaphoreTake(g_ackSem, 0) == pdTRUE) {}
    g_ackFinal = false;

    // Chunk at 244 bytes (matches pypixelcolor chunk_size for MTU=247).
    const size_t CHUNK = 244;
    for (size_t off = 0; off < totalLen; off += CHUNK) {
        size_t n = (totalLen - off);
        if (n > CHUNK) n = CHUNK;
        if (!g_writeChar->writeValue(frame + off, n, true)) {
            Serial.printf("[ble] write failed at off=%u\n", (unsigned)off);
            return false;
        }
    }

    // Window ack should arrive within a few hundred ms; allow more headroom.
    if (xSemaphoreTake(g_ackSem, pdMS_TO_TICKS(3000)) != pdTRUE) {
        Serial.println("[ble] window ack timeout");
        return false;
    }
    // Final ack often piggybacks the window ack on single-window sends;
    // give it a short grace period if it hasn't arrived yet.
    if (!g_ackFinal) {
        xSemaphoreTake(g_ackSem, pdMS_TO_TICKS(1500));
    }
    return true;
}
