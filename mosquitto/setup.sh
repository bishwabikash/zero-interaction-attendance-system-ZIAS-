#!/usr/bin/env bash
# Bootstrap Mosquitto auth: create the password file and copy the ACL template.
# Run once after cloning:
#   MQTT_BACKEND_PASSWORD=... ./mosquitto/setup.sh
# Then restart the mosquitto container.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CONF_DIR="$HERE/config"
PWD_FILE="$CONF_DIR/passwd"
ACL_FILE="$CONF_DIR/acl"

BACKEND_USER="${MQTT_BACKEND_USER:-zias-backend}"
BACKEND_PASS="${MQTT_BACKEND_PASSWORD:-}"

if [[ -z "$BACKEND_PASS" ]]; then
    echo "ERROR: export MQTT_BACKEND_PASSWORD before running." >&2
    exit 1
fi

command -v mosquitto_passwd >/dev/null 2>&1 || {
    echo "mosquitto_passwd not found. Install mosquitto (apt install mosquitto) or" >&2
    echo "run this inside the eclipse-mosquitto container:" >&2
    echo "  docker run --rm -v \$(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto:2 \\" >&2
    echo "      mosquitto_passwd -b /mosquitto/config/passwd $BACKEND_USER \$MQTT_BACKEND_PASSWORD" >&2
    exit 1
}

: > "$PWD_FILE"
mosquitto_passwd -b "$PWD_FILE" "$BACKEND_USER" "$BACKEND_PASS"
chmod 640 "$PWD_FILE"

if [[ ! -f "$ACL_FILE" ]]; then
    cp "$CONF_DIR/acl.example" "$ACL_FILE"
fi

echo "Password file written with user '$BACKEND_USER'."
echo "Add per-node users with:"
echo "  mosquitto_passwd -b $PWD_FILE <device_id> <password>"
