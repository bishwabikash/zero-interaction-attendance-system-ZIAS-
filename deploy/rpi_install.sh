#!/usr/bin/env bash
# One-shot installer for a Raspberry Pi (Bookworm 64-bit) acting as the
# ZIAS server. Idempotent — safe to re-run.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<you>/zias/main/deploy/rpi_install.sh | sudo bash
# or, after cloning:
#   sudo bash deploy/rpi_install.sh

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root (sudo)." >&2
    exit 1
fi

REPO_DIR="${REPO_DIR:-/opt/zias}"
BRANCH="${BRANCH:-master}"
GIT_URL="${GIT_URL:-https://github.com/bishwabikash/zero-interaction-attendance-system-ZIAS-.git}"

echo "[1/5] Installing prerequisites..."
apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates curl git gnupg apt-transport-https openssl python3-pip

if ! command -v docker >/dev/null 2>&1; then
    echo "[2/5] Installing Docker Engine..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian $codename stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    usermod -aG docker "${SUDO_USER:-pi}" || true
else
    echo "[2/5] Docker already installed — skipping."
fi

echo "[3/5] Cloning repository to $REPO_DIR..."
if [[ ! -d "$REPO_DIR/.git" ]]; then
    git clone --branch "$BRANCH" --depth 1 "$GIT_URL" "$REPO_DIR"
else
    git -C "$REPO_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$REPO_DIR" checkout "$BRANCH"
    git -C "$REPO_DIR" reset --hard "origin/$BRANCH"
fi
chown -R "${SUDO_USER:-pi}":"${SUDO_USER:-pi}" "$REPO_DIR"

echo "[4/5] Generating .env if missing..."
ENV_FILE="$REPO_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    randpw() { openssl rand -base64 24 | tr -d '\n=/+' | cut -c1-24; }
    randhex() { openssl rand -hex 32; }
    cat > "$ENV_FILE" <<EOF
DB_HOST=db
DB_PORT=3306
DB_NAME=iot_data
DB_USER=zias
DB_PASSWORD=$(randpw)
DB_ROOT_PASSWORD=$(randpw)

REDIS_HOST=redis
REDIS_PORT=6379

MQTT_BROKER=mosquitto
MQTT_PORT=1883
MQTT_BACKEND_USER=zias-backend
MQTT_BACKEND_PASSWORD=$(randpw)

JWT_SECRET_KEY=$(randhex)
CORS_ORIGINS=http://localhost,http://$(hostname -I | awk '{print $1}')

BOOTSTRAP_ADMIN_USER=admin
BOOTSTRAP_ADMIN_PASSWORD=$(randpw)

VITE_API_URL=/
EOF
    chmod 600 "$ENV_FILE"
    echo "  -> wrote $ENV_FILE (chmod 600). Save the admin password from it now."
fi

echo "[5/5] Provisioning Mosquitto credentials and starting stack..."
set +u; source "$ENV_FILE"; set -u
mkdir -p "$REPO_DIR/mosquitto/config"
if [[ ! -f "$REPO_DIR/mosquitto/config/passwd" ]]; then
    docker run --rm -v "$REPO_DIR/mosquitto/config:/mosquitto/config" \
        eclipse-mosquitto:2 mosquitto_passwd -b -c /mosquitto/config/passwd \
        "$MQTT_BACKEND_USER" "$MQTT_BACKEND_PASSWORD"
fi
[[ -f "$REPO_DIR/mosquitto/config/acl" ]] || \
    cp "$REPO_DIR/mosquitto/config/acl.example" "$REPO_DIR/mosquitto/config/acl"

install -m 0644 "$REPO_DIR/deploy/zias.service" /etc/systemd/system/zias.service
systemctl daemon-reload
systemctl enable --now zias.service

echo
echo "ZIAS is starting. Watch progress with: sudo systemctl status zias"
echo "Admin credentials are in $ENV_FILE (BOOTSTRAP_ADMIN_*)."
