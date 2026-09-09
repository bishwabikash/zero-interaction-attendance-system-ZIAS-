# ESP32 Node — Build & Flash Guide

## Bill of materials (per node, INR)

| Part | Typical cost |
|------|-------------:|
| ESP32 DevKit (30-pin, WROOM-32) | ₹250-350 |
| MFRC522 RFID reader + 2 keychains + 1 card | ₹100-150 |
| HC-SR501 PIR sensor | ₹50-80 |
| 5 V / 1 A USB-C power adapter | ₹120-180 |
| Enclosure + wires | ₹100-200 |
| **Total** | **₹620-960** |

For an ESP32-CAM (optional face-recognition) add ₹450-600.

## Wiring

MFRC522 → ESP32 (default SPI, exposed on GPIO 18/19/23):

| MFRC522 pin | ESP32 pin |
|-------------|-----------|
| SDA / SS    | GPIO 21   |
| SCK         | GPIO 18   |
| MOSI        | GPIO 23   |
| MISO        | GPIO 19   |
| IRQ         | (unused)  |
| GND         | GND       |
| RST         | GPIO 22   |
| 3.3 V       | 3.3 V     |

HC-SR501 → ESP32:

| PIR pin | ESP32 pin |
|---------|-----------|
| VCC     | 5 V       |
| GND     | GND       |
| OUT     | GPIO 4    |

Set the PIR trim pots so the retrigger delay is ~2 s and sensitivity is
about 50%.

## Software

1. Install [Arduino IDE 2](https://www.arduino.cc/en/software) and add
   the ESP32 board package (`https://espressif.github.io/arduino-esp32/package_esp32_index.json`).
2. Install libraries via Library Manager: `MFRC522`, `PubSubClient`,
   `ArduinoJson (≥6.x)`. For the optional beacon: `ESP32 BLE Arduino`.
3. Copy `hardware/esp32_universal/config.h.example` to
   `hardware/esp32_universal/config.h` and fill in:
   - `WIFI_SSID`, `WIFI_PASSWORD`
   - `DEVICE_NAME` (unique — this is also the MQTT username; e.g.
     `room101_door_in`, `room101_door_out`)
   - `DEVICE_DIRECTION` (`entry` on the outside-of-door node,
     `exit` on the inside-of-door node)
   - `CLUSTER_ID` (the room number is a good default)
   - `MQTT_BROKER` (your Raspberry Pi's IP or hostname)
   - Uncomment `MQTT_USERNAME` / `MQTT_PASSWORD` to enable auth.
4. Board: **ESP32 Dev Module**, Flash Size: 4 MB, Partition Scheme:
   **Default 4MB with spiffs**, Upload speed: 921600.
5. Compile & upload.

The serial monitor at 115200 baud shows detection results, WiFi/MQTT
state and every event as it publishes.

## Provisioning a node on the server

Once the firmware is running the node needs a matching MQTT credential
and a device record.

```bash
# On the Pi (adjust the password):
docker compose exec mosquitto mosquitto_passwd -b /mosquitto/config/passwd \
    room101_door_in "<node-password>"
docker compose restart mosquitto

# Register the device (needs the admin JWT — get it from /api/v1/auth/login):
curl -X POST http://<pi>/api/v1/devices/register \
    -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
    -d '{"device_id":"room101_door_in","cluster_id":101,"direction":"entry","room_value":"Room 101"}'
```

## Two-node "entry + exit" pairing

For accurate direction detection, place two nodes at each door: one on
the outside with `DEVICE_DIRECTION=entry`, one on the inside with
`DEVICE_DIRECTION=exit`. Same `CLUSTER_ID`, different `DEVICE_NAME`.
The backend uses the `direction` field on `user_devices`, not the
name suffix — so any naming scheme works.

## OTA updates (optional)

Add [`ArduinoOTA`](https://docs.arduino.cc/tutorials/generic/basic-ota/)
inside `setup()` and subscribe to `zias/devices/<id>/cmd` for a signed
update URL. See `docs/OTA.md` for a template (roadmap).
