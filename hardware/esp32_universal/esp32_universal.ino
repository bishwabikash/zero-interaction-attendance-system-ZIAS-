/*
 * ZIAS ESP32 Universal Node - Firmware 2.1
 *
 * Auto-detects RFID (MFRC522), PIR, optional BLE beacon and optional
 * ESP32-CAM. Publishes events over MQTT with QoS 1, keeps a small
 * offline queue in NVS, uses NTP for wall-clock timestamps, and
 * feeds the hardware watchdog.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Preferences.h>
#include <time.h>
#include <esp_task_wdt.h>

#include "config.h"

#ifdef ENABLE_BLE
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEBeacon.h>
#endif

#ifdef CAMERA_MODEL_AI_THINKER
#include "esp_camera.h"
#endif

#ifndef WDT_TIMEOUT_SECONDS
#define WDT_TIMEOUT_SECONDS 30
#endif
#ifndef PIR_DEBOUNCE_MS
#define PIR_DEBOUNCE_MS 1500
#endif
#ifndef RFID_COOLDOWN_MS
#define RFID_COOLDOWN_MS 3000
#endif
#ifndef MQTT_KEEPALIVE_S
#define MQTT_KEEPALIVE_S 30
#endif
#ifndef HEARTBEAT_INTERVAL_MS
#define HEARTBEAT_INTERVAL_MS 60000
#endif
#ifndef OFFLINE_QUEUE_MAX
#define OFFLINE_QUEUE_MAX 32
#endif
#ifndef NTP_SERVER
#define NTP_SERVER "pool.ntp.org"
#endif
#ifndef TZ_OFFSET_SECONDS
#define TZ_OFFSET_SECONDS 19800  // Asia/Kolkata default (+05:30)
#endif

static bool hasRFID = false;
static bool hasPIR = false;
static bool hasBLE = false;
static bool hasCamera = false;

static MFRC522 *rfid = nullptr;
static WiFiClient wifiClient;
static PubSubClient mqttClient(wifiClient);
static Preferences prefs;

static unsigned long lastMotionMs = 0;
static unsigned long lastReconnectMs = 0;
static unsigned long lastHeartbeatMs = 0;
static char lastRfidSeen[32] = {0};
static unsigned long lastRfidTimeMs = 0;

// forward declarations
static void detectHardware();
static bool connectWiFi();
static bool connectMQTT();
static void mqttCallback(char *topic, byte *payload, unsigned int length);
static void publishSensorEvent(const char *eventType, const char *rfidUid);
static void publishDeviceStatus(const char *status);
static String readRFID();
static void setupBLEBeacon();
static void syncTime();
static uint64_t currentEpochMs();
static void queueOffline(const String &topic, const String &payload);
static void drainOfflineQueue();

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=== ZIAS ESP32 Node v2.1 ===");
    Serial.printf("device_id=%s cluster=%d direction=%s\n",
                  DEVICE_NAME, CLUSTER_ID, DEVICE_DIRECTION);

    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH);

    prefs.begin("zias", false);

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
    {
        esp_task_wdt_config_t wdt_cfg = {};
        wdt_cfg.timeout_ms = (uint32_t) WDT_TIMEOUT_SECONDS * 1000U;
        wdt_cfg.idle_core_mask = 0;
        wdt_cfg.trigger_panic = true;
        esp_task_wdt_reconfigure(&wdt_cfg);
    }
#else
    esp_task_wdt_init(WDT_TIMEOUT_SECONDS, true);
#endif
    esp_task_wdt_add(NULL);

    detectHardware();
    if (!connectWiFi()) {
        Serial.println("WiFi failed; will retry in loop");
    } else {
        syncTime();
    }

    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(mqttCallback);
    mqttClient.setKeepAlive(MQTT_KEEPALIVE_S);
    mqttClient.setBufferSize(512);

    if (hasRFID) {
        SPI.begin();
        rfid = new MFRC522(GPIO_RFID_SS, GPIO_RFID_RST);
        rfid->PCD_Init();
    }
    if (hasPIR) pinMode(GPIO_PIR, INPUT);
    if (hasBLE) setupBLEBeacon();
}

static void detectHardware() {
    Serial.println("[detect] scanning...");

    SPI.begin();
    MFRC522 probe(GPIO_RFID_SS, GPIO_RFID_RST);
    probe.PCD_Init();
    delay(50);
    byte version = probe.PCD_ReadRegister(MFRC522::VersionReg);
    hasRFID = (version == 0x91 || version == 0x92);
    Serial.printf("[detect] RFID=%s (v=0x%02X)\n", hasRFID ? "YES" : "NO", version);

    hasPIR = true;
    Serial.printf("[detect] PIR=YES (gpio=%d)\n", GPIO_PIR);

#ifdef ENABLE_BLE
    hasBLE = true;
    Serial.println("[detect] BLE=YES");
#else
    hasBLE = false;
#endif

#ifdef CAMERA_MODEL_AI_THINKER
    camera_config_t config = {};
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    hasCamera = (esp_camera_init(&config) == ESP_OK);
    Serial.printf("[detect] Camera=%s\n", hasCamera ? "YES" : "NO");
#endif
}

static bool connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return true;
    Serial.printf("[wifi] connecting to %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT) {
        esp_task_wdt_reset();
        delay(250);
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[wifi] ip=%s rssi=%d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
        return true;
    }
    Serial.println("[wifi] failed");
    return false;
}

static void syncTime() {
    configTime(TZ_OFFSET_SECONDS, 0, NTP_SERVER, "time.google.com", "time.cloudflare.com");
    struct tm t;
    uint32_t start = millis();
    while (!getLocalTime(&t, 500) && millis() - start < 8000) {
        esp_task_wdt_reset();
    }
    Serial.printf("[time] epoch=%llu\n", (unsigned long long) currentEpochMs());
}

static uint64_t currentEpochMs() {
    time_t now = time(nullptr);
    if (now < 1700000000) return 0;
    return (uint64_t) now * 1000ULL;
}

static bool connectMQTT() {
    if (mqttClient.connected()) return true;
    String clientId = String("zias-") + DEVICE_NAME + "-" + String((uint32_t) ESP.getEfuseMac(), HEX);
    String willTopic = String(MQTT_TOPIC_PREFIX) + "/devices/" + DEVICE_NAME + "/status";
    const char *willMsg = "{\"status\":\"offline\"}";

#ifdef MQTT_USERNAME
    bool ok = mqttClient.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD,
                                 willTopic.c_str(), 1, true, willMsg);
#else
    bool ok = mqttClient.connect(clientId.c_str(), NULL, NULL,
                                 willTopic.c_str(), 1, true, willMsg);
#endif

    if (ok) {
        Serial.println("[mqtt] connected");
        String cmdTopic = String(MQTT_TOPIC_PREFIX) + "/devices/" + DEVICE_NAME + "/cmd";
        mqttClient.subscribe(cmdTopic.c_str(), 1);
        publishDeviceStatus("online");
        drainOfflineQueue();
        return true;
    }
    Serial.printf("[mqtt] connect failed rc=%d\n", mqttClient.state());
    return false;
}

static void mqttCallback(char *topic, byte *payload, unsigned int length) {
    // Reserved for OTA / config updates. Kept minimal — anything larger
    // belongs in a signed OTA channel.
    Serial.printf("[mqtt] cmd %s (%u bytes)\n", topic, length);
}

static void publishSensorEvent(const char *eventType, const char *rfidUid) {
    StaticJsonDocument<256> doc;
    doc["device_id"] = DEVICE_NAME;
    doc["cluster_id"] = CLUSTER_ID;
    doc["direction"] = DEVICE_DIRECTION;
    doc["event_type"] = eventType;
    doc["ts_ms"] = currentEpochMs();
    doc["uptime_ms"] = (uint32_t) millis();
    if (rfidUid && rfidUid[0]) doc["rfid"] = rfidUid;
    if (hasPIR) doc["sensor"] = true;

    char payload[256];
    size_t n = serializeJson(doc, payload, sizeof(payload));

    String topic = String(MQTT_TOPIC_PREFIX) + "/devices/" + DEVICE_NAME + "/sensor";
    if (mqttClient.connected() && mqttClient.publish(topic.c_str(), (const uint8_t *) payload, n, false)) {
        Serial.printf("[pub] %s\n", payload);
    } else {
        queueOffline(topic, String(payload));
    }
}

static void publishDeviceStatus(const char *status) {
    StaticJsonDocument<384> doc;
    doc["device_id"] = DEVICE_NAME;
    doc["status"] = status;
    doc["direction"] = DEVICE_DIRECTION;
    doc["has_rfid"] = hasRFID;
    doc["has_pir"] = hasPIR;
    doc["has_ble"] = hasBLE;
    doc["has_camera"] = hasCamera;
    doc["ip"] = WiFi.localIP().toString();
    doc["rssi"] = WiFi.RSSI();
    doc["firmware_version"] = "2.1";
    doc["ts_ms"] = currentEpochMs();

    char payload[384];
    size_t n = serializeJson(doc, payload, sizeof(payload));

    String topic = String(MQTT_TOPIC_PREFIX) + "/devices/" + DEVICE_NAME + "/status";
    mqttClient.publish(topic.c_str(), (const uint8_t *) payload, n, true);
    Serial.printf("[status] %s\n", payload);
}

static String readRFID() {
    if (!hasRFID || !rfid) return "";
    if (!rfid->PICC_IsNewCardPresent() || !rfid->PICC_ReadCardSerial()) return "";

    char buf[32];
    size_t pos = 0;
    for (byte i = 0; i < rfid->uid.size && pos + 3 < sizeof(buf); i++) {
        if (i) buf[pos++] = ' ';
        snprintf(&buf[pos], sizeof(buf) - pos, "%02X", rfid->uid.uidByte[i]);
        pos += 2;
    }
    buf[pos] = '\0';
    rfid->PICC_HaltA();
    return String(buf);
}

static void setupBLEBeacon() {
#ifdef ENABLE_BLE
    BLEDevice::init(DEVICE_NAME);
    BLEServer *server = BLEDevice::createServer();
    (void) server;
    BLEAdvertising *adv = BLEDevice::getAdvertising();

    BLEBeacon beacon;
    beacon.setManufacturerId(0x4C00);
    beacon.setProximityUUID(BLEUUID(BLE_BEACON_UUID));
    beacon.setMajor(CLUSTER_ID);
    beacon.setMinor(1);

    BLEAdvertisementData data;
    data.setFlags(0x06);
    data.setManufacturerData(beacon.getData());
    adv->setAdvertisementData(data);
    adv->start();
#endif
}

static inline String qKey(const char *prefix, uint32_t idx) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%s%u", prefix, (unsigned) idx);
    return String(buf);
}

static void queueOffline(const String &topic, const String &payload) {
    uint32_t count = prefs.getUInt("q_count", 0);
    if (count >= OFFLINE_QUEUE_MAX) {
        Serial.println("[queue] full, dropping oldest");
        for (uint32_t i = 1; i < count; i++) {
            prefs.putString(qKey("q_t", i - 1).c_str(), prefs.getString(qKey("q_t", i).c_str()));
            prefs.putString(qKey("q_p", i - 1).c_str(), prefs.getString(qKey("q_p", i).c_str()));
        }
        count = OFFLINE_QUEUE_MAX - 1;
    }
    prefs.putString(qKey("q_t", count).c_str(), topic);
    prefs.putString(qKey("q_p", count).c_str(), payload);
    prefs.putUInt("q_count", count + 1);
    Serial.printf("[queue] stored (%u total)\n", count + 1);
}

static void drainOfflineQueue() {
    uint32_t count = prefs.getUInt("q_count", 0);
    if (!count) return;
    Serial.printf("[queue] draining %u events\n", count);
    for (uint32_t i = 0; i < count; i++) {
        String topic = prefs.getString(qKey("q_t", i).c_str());
        String payload = prefs.getString(qKey("q_p", i).c_str());
        if (topic.length() && !mqttClient.publish(topic.c_str(), payload.c_str())) {
            Serial.println("[queue] resend failed; aborting drain");
            return;
        }
    }
    for (uint32_t i = 0; i < count; i++) {
        prefs.remove(qKey("q_t", i).c_str());
        prefs.remove(qKey("q_p", i).c_str());
    }
    prefs.putUInt("q_count", 0);
}

void loop() {
    esp_task_wdt_reset();

    if (WiFi.status() != WL_CONNECTED) {
        connectWiFi();
    }

    if (!mqttClient.connected()) {
        unsigned long now = millis();
        if (now - lastReconnectMs > MQTT_RECONNECT_DELAY) {
            lastReconnectMs = now;
            connectMQTT();
        }
    } else {
        mqttClient.loop();
    }

    if (currentEpochMs() == 0 && WiFi.status() == WL_CONNECTED) {
        syncTime();
    }

    if (hasPIR && digitalRead(GPIO_PIR) == HIGH) {
        unsigned long now = millis();
        if (now - lastMotionMs >= PIR_DEBOUNCE_MS) {
            lastMotionMs = now;
            digitalWrite(LED_BUILTIN, LOW);

            String uid = "";
            uint32_t rfidStart = millis();
            while (millis() - rfidStart < 800) {
                uid = readRFID();
                if (uid.length()) break;
                esp_task_wdt_reset();
                delay(30);
            }

            if (uid.length()) {
                bool sameCard = strncmp(uid.c_str(), lastRfidSeen, sizeof(lastRfidSeen)) == 0;
                if (!sameCard || (now - lastRfidTimeMs) >= RFID_COOLDOWN_MS) {
                    strncpy(lastRfidSeen, uid.c_str(), sizeof(lastRfidSeen) - 1);
                    lastRfidTimeMs = now;
                    publishSensorEvent("activated", uid.c_str());
                }
            } else if (!hasRFID) {
                publishSensorEvent("motion", nullptr);
            }
            digitalWrite(LED_BUILTIN, HIGH);
        }
    }

    if (millis() - lastHeartbeatMs > HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatMs = millis();
        if (mqttClient.connected()) publishDeviceStatus("heartbeat");
    }
}
