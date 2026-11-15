"""Legacy cron entrypoint — DEPRECATED.

ZIAS 2.x processes events in real time via `mqtt.event_processor`, not a
polling cron job. If your deployment still calls this file every minute
(from the ESP8266 era), remove the crontab entry — the service running
`python -m mqtt.event_processor` handles it now.

For emergency backfill from raw sensor_data rows (e.g. after MQTT downtime),
run `python -m scripts.backfill_events` (add per your needs).
"""

import sys


def main() -> int:
    sys.stderr.write(
        "master_cron.py is deprecated in ZIAS 2.x — event_processor handles "
        "attendance in real time. Remove this from cron.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
