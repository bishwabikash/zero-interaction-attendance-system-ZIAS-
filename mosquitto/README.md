# Mosquitto for ZIAS

Anonymous access is disabled. The broker needs a password file at
`mosquitto/config/passwd` and an ACL at `mosquitto/config/acl` before the
container will start accepting connections.

## First-time setup

```bash
export MQTT_BACKEND_PASSWORD='<long-random-string>'
./mosquitto/setup.sh
```

That writes the credentials for the backend service (username defaults to
`zias-backend`) and copies `acl.example` to `acl`.

## Adding an ESP32 node

Each node authenticates as its own `device_id`:

```bash
docker exec -it zias_mosquitto mosquitto_passwd -b /mosquitto/config/passwd \
    room101_door_in <node-password>
```

The pattern ACL restricts every node to `zias/devices/<its-own-id>/…` topics.

## TLS (recommended for anything beyond a lab)

1. Generate certs (Let's Encrypt or an internal CA) and drop `ca.crt`,
   `server.crt`, `server.key` into `mosquitto/config/certs/`.
2. Add a TLS listener to `mosquitto.conf`:

   ```
   listener 8883
   protocol mqtt
   cafile   /mosquitto/config/certs/ca.crt
   certfile /mosquitto/config/certs/server.crt
   keyfile  /mosquitto/config/certs/server.key
   require_certificate false
   ```

3. Set `MQTT_TLS=true` in the backend `.env` and enable TLS on the ESP32
   firmware via `wifiClient` → `WiFiClientSecure`.
