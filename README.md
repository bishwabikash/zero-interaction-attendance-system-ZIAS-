# Zero Interaction Attendance System (ZIAS)

Low-cost, contactless attendance for schools and colleges. Students walk
past a doorway sensor with an RFID card — the system logs entry and exit
automatically. Runs on a Raspberry Pi 4/5 as the server and ESP32 nodes at
each door. Everything is open source and offline-first.

## What's in this repository

| Path                        | What it is                                              |
|-----------------------------|---------------------------------------------------------|
| `hardware/esp32_universal/` | ESP32 firmware (RFID + PIR + optional BLE + camera)    |
| `backend/`                  | FastAPI service, MQTT event processor, DB models       |
| `frontend/`                 | React + Tailwind admin dashboard                       |
| `mosquitto/`                | Broker config, ACL template, credential setup script   |
| `deploy/`                   | Raspberry Pi install script + systemd unit             |
| `docs/`                     | Schema, Pi deploy guide, ESP32 flashing guide          |

## Architecture

```
   ┌──────────────────────────────────────────────┐
   │              Doors / rooms (per site)         │
   │  ┌───────────────┐         ┌───────────────┐ │
   │  │ ESP32 outside │──┐   ┌──│ ESP32 inside  │ │
   │  │ direction=in  │  │   │  │ direction=out │ │
   │  └───────────────┘  │   │  └───────────────┘ │
   └────────────Wi-Fi────┼───┼────────────────────┘
                         ▼   ▼
                    ┌───────────────┐
                    │  Mosquitto    │◄─── Mobile app (optional BLE)
                    │  MQTT broker  │
                    └──────┬────────┘
                           │
                    ┌──────▼────────┐        ┌──────────────┐
                    │ FastAPI       │◄──────►│  MariaDB     │
                    │ + event       │        └──────────────┘
                    │ processor     │        ┌──────────────┐
                    └──────┬────────┘◄──────►│  Redis       │
                           │                 └──────────────┘
                    ┌──────▼────────┐
                    │ React admin   │
                    │ dashboard     │
                    └───────────────┘

     ─── All services run on ONE Raspberry Pi (docker compose) ───
```

Every service ships as a Docker container. The Pi hosts them all.

## Cost per site

| Layer | Item | Approx cost (INR) |
|-------|------|-------------------:|
| Server (once per school) | Raspberry Pi 4 4 GB + PSU + 64 GB SD + case | ₹6,500 |
| Per door (2 nodes) | 2× ESP32 + 2× MFRC522 + 2× PIR + power + enclosure | ₹1,600 |
| Per student | 1 RFID card / keychain | ₹15-30 |

Example: a 500-student school with 8 doorways ≈ ₹6,500 + 8 × ₹1,600 +
500 × ₹25 = **~₹32,000 (~USD 380)** for the entire deployment.

## Quick start (Raspberry Pi)

1. Flash Raspberry Pi OS Lite 64-bit and SSH in.
2. Run the installer:
   ```bash
   git clone https://github.com/bishwabikash/zero-interaction-attendance-system-ZIAS-.git
   cd zero-interaction-attendance-system-ZIAS-
   sudo bash deploy/rpi_install.sh
   ```
3. Read the generated admin password from `/opt/zias/.env` and log in at
   `http://<pi-ip>/`.

Full details: [`docs/DEPLOYMENT_RPI.md`](docs/DEPLOYMENT_RPI.md).

## Building the ESP32 nodes

See [`docs/ESP32_FLASHING.md`](docs/ESP32_FLASHING.md). Two nodes per
door — one marked `direction=entry`, one `direction=exit`.

## Local development

```bash
cp .env.example .env       # fill in every empty value
docker compose up --build
docker compose exec api python -m scripts.seed_admin
```

Then the API is on `http://localhost:8000` (docs at `/docs`) and the
dashboard on `http://localhost/`.

## How the pairing works

Each doorway has two nodes:

- `direction=entry` on the outside — its RFID scan means the student
  entered the room.
- `direction=exit` on the inside — the same card scanned here means they
  left.

The backend uses that `direction` field on `user_devices` (not any naming
heuristic) to decide `status = +1 | -1` in `entry_log`. An anti-tailgating
window (default 3 s) suppresses accidental double-logs.

## What was fixed in v2.1

- Real user / JWT auth (dropped the `admin/admin` demo).
- Broken imports (`api.auth`) — every route module now loads at startup.
- ESP32 firmware: NTP wall-clock, offline queue in NVS, MQTT auth + LWT,
  hardware watchdog, per-card debounce, non-blocking motion loop.
- Direction detection uses an explicit `direction` field instead of the
  fragile even/odd device-name suffix.
- MQTT: anonymous access disabled, per-device ACLs.
- WebSocket `/ws` broadcasting for the admin dashboard.
- Raspberry-Pi-aware Docker compose overlay + one-shot installer +
  systemd unit.
- Health check that actually queries DB/Redis/MQTT.
- Schema and models are now the same story.

## Security notes

- The generated `.env` contains real secrets. Chmod 600, keep it off git.
- Enable TLS on Mosquitto for anything beyond a private VLAN
  (`mosquitto/README.md`).
- Rotate `JWT_SECRET_KEY` on a schedule; every rotation invalidates
  existing tokens.
- The `/health` endpoint is unauthenticated by design — put it behind a
  private network or add an IP allowlist at the reverse proxy.

## License

GNU AGPL v3.0 — see `LICENSE`.

## Support

Please open a GitHub issue; PRs welcome.
