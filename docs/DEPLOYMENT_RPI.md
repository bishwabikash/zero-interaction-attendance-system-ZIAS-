# Raspberry Pi Server Deployment

ZIAS runs comfortably on a Raspberry Pi 4 (4 GB) or Pi 5 in a school-wide
deployment of up to ~2,000 students and 40 ESP32 nodes. This document is
the ground-truth setup.

## Recommended hardware

| Component | Model | Notes |
|-----------|-------|-------|
| Server | Raspberry Pi 4 (4 GB) or Pi 5 | Pi 5 recommended >5,000 students |
| Storage | 64 GB Class-10 SD **or** SSD via USB 3 | SSD dramatically reduces MariaDB latency |
| Power | Official 27 W USB-C PSU | Under-voltage corrupts data |
| Network | Wired Ethernet | Wi-Fi acceptable, wired is safer |
| Cooling | Passive heatsink + case fan | Sustained 100% load without throttling |
| UPS (optional) | Any 12 V/2 A UPS HAT | Survives power blips |

## OS

Install **Raspberry Pi OS Lite 64-bit (Bookworm)** using Raspberry Pi
Imager. Enable SSH from Imager's advanced menu, set a strong password,
attach it to your Wi-Fi or Ethernet.

Update once you can log in:

```bash
sudo apt update && sudo apt full-upgrade -y && sudo reboot
```

## One-shot install

```bash
git clone https://github.com/bishwabikash/zero-interaction-attendance-system-ZIAS-.git
cd zero-interaction-attendance-system-ZIAS-
sudo bash deploy/rpi_install.sh
```

The script:

1. Installs Docker Engine + Compose v2.
2. Clones ZIAS to `/opt/zias`.
3. Generates a locked-down `.env` with random credentials (JWT secret,
   DB passwords, MQTT password, admin password).
4. Creates the Mosquitto password file for the backend user.
5. Installs and enables the `zias.service` systemd unit so the whole
   stack comes up automatically at boot.

After the first boot, print the generated admin password:

```bash
sudo grep BOOTSTRAP_ADMIN_PASSWORD /opt/zias/.env
```

Save it. Then log in at `http://<pi-ip>/`.

## Manual install

If you'd rather do it by hand:

```bash
sudo apt install -y docker.io docker-compose-plugin openssl
git clone https://github.com/bishwabikash/zero-interaction-attendance-system-ZIAS-.git /opt/zias
cd /opt/zias
cp .env.example .env
# Edit .env — set every empty password and JWT_SECRET_KEY (>=32 chars).

# Create MQTT password
docker run --rm -v $(pwd)/mosquitto/config:/mosquitto/config \
    eclipse-mosquitto:2 mosquitto_passwd -b -c /mosquitto/config/passwd \
    zias-backend "$MQTT_BACKEND_PASSWORD"
cp mosquitto/config/acl.example mosquitto/config/acl

# Boot the stack
docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d
docker compose exec api python -m scripts.seed_admin
```

## Everyday operations

```bash
# Status
sudo systemctl status zias
docker compose -f /opt/zias/docker-compose.yml -f /opt/zias/docker-compose.rpi.yml ps

# Logs
docker compose logs -f api processor

# Backup the database
docker compose exec db mariadb-dump -uroot -p$DB_ROOT_PASSWORD iot_data \
    | gzip > /opt/zias/backups/iot_data-$(date +%F).sql.gz

# Add a new ESP32 device to MQTT
docker compose exec mosquitto mosquitto_passwd -b /mosquitto/config/passwd \
    room101_door_in <node-password>
docker compose restart mosquitto
```

## Sizing guidance

| Students | Nodes | Suggested Pi | Storage |
|----------|-------|--------------|---------|
| ≤ 500    | ≤ 10  | Pi 4 (2 GB)  | SD 32 GB |
| ≤ 2,000  | ≤ 40  | Pi 4 (4 GB)  | SD 64 GB |
| ≤ 5,000  | ≤ 100 | Pi 4 (8 GB) or Pi 5 | SSD 128 GB |
| > 5,000  | > 100 | Pi 5 (8 GB) or x86 mini-PC | SSD 256 GB |

## Hardening checklist

- [ ] Change `BOOTSTRAP_ADMIN_PASSWORD` after first login and rotate the
      env value or delete it.
- [ ] Change the Pi's default `pi` user password / disable it.
- [ ] `sudo ufw enable && sudo ufw allow 22,80,1883/tcp`.
- [ ] Put the Pi and ESP32 nodes on a dedicated VLAN or SSID.
- [ ] Turn on TLS on Mosquitto (see `mosquitto/README.md`).
- [ ] Rotate `JWT_SECRET_KEY` yearly; all users must re-log-in.
- [ ] Configure automatic offsite backup of `/opt/zias/backups`.
