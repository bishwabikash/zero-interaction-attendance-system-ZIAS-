"""Event processor: turns raw sensor/BLE events into attendance records."""

import asyncio
import json
import signal
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import redis.asyncio as redis

from api.config import settings
from api.database import get_db_session
from api.db_models import (
    BLEEvent,
    DeviceStatusEnum,
    DirectionEnum,
    EntryLog,
    SensorData,
    Student,
    UserDevice,
)


def _parse_ts(value: Optional[str]) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.utcnow()
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


class EventProcessor:
    def __init__(self) -> None:
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe("zias:events")
        print("[proc] subscribed to zias:events")

        try:
            async for message in self.pubsub.listen():
                if self._stop.is_set():
                    break
                if message.get("type") == "message":
                    await self._safe_process(message["data"])
        finally:
            await self.stop()

    async def _safe_process(self, data) -> None:
        try:
            event = json.loads(data.decode() if isinstance(data, bytes) else data)
            kind = event.get("type")
            if kind == "sensor":
                await self._process_sensor(event)
            elif kind == "ble":
                await self._process_ble(event)
            elif kind == "status":
                await self._process_status(event)
        except Exception as exc:
            print(f"[proc] error: {exc}")

    async def _process_sensor(self, event: Dict[str, Any]) -> None:
        device_id = event.get("device_id")
        rfid = event.get("rfid")
        cluster_id = event.get("cluster_id")
        received_at = _parse_ts(event.get("received_at"))

        with get_db_session() as db:
            device = db.query(UserDevice).filter(UserDevice.device_id == device_id).first()
            if not device:
                print(f"[proc] unknown device {device_id} — skipping")
                return

            db.add(
                SensorData(
                    device_ID=device_id,
                    cluster_ID=cluster_id if cluster_id is not None else device.cluster_ID,
                    RFID=rfid,
                    time_stamp=received_at,
                    sensor_active=bool(event.get("sensor_active", True)),
                    processed=bool(rfid),
                )
            )

            if not rfid:
                db.commit()
                return

            if self._is_tailgate(db, rfid, device.room_value, received_at):
                db.commit()
                return

            student = db.query(Student).filter(Student.RFID == rfid).first()
            status_int = self._infer_direction(device)

            log = EntryLog(
                student_id=student.student_id if student else None,
                student_name=student.stud_name if student else "Unknown",
                RFID=rfid,
                room_value=device.room_value,
                status=status_int,
                timestamp=received_at,
                confidence=0.95,
                source="rfid",
            )
            db.add(log)
            db.commit()
            direction_label = "entry" if status_int == 1 else "exit"
            print(f"[proc] logged {direction_label} for {log.student_name} @ {device.room_value}")

    @staticmethod
    def _infer_direction(device: UserDevice) -> int:
        if device.direction == DirectionEnum.EXIT:
            return -1
        return 1

    @staticmethod
    def _is_tailgate(db, rfid: str, room: str, now: datetime) -> bool:
        cutoff = now - timedelta(seconds=settings.ANTI_TAILGATING_DELAY_SECONDS)
        recent = (
            db.query(EntryLog)
            .filter(
                EntryLog.RFID == rfid,
                EntryLog.room_value == room,
                EntryLog.timestamp >= cutoff,
            )
            .first()
        )
        if recent:
            print(f"[proc] tailgate suppressed for {rfid} @ {room}")
            return True
        return False

    async def _process_ble(self, event: Dict[str, Any]) -> None:
        with get_db_session() as db:
            db.add(
                BLEEvent(
                    student_id=event.get("student_id"),
                    beacon_uuid=event.get("beacon_uuid") or "",
                    rssi=event.get("rssi"),
                    latitude=(event.get("location") or {}).get("latitude"),
                    longitude=(event.get("location") or {}).get("longitude"),
                    event_type=event.get("event_type", "approaching"),
                    app_version=event.get("app_version", ""),
                    timestamp=_parse_ts(event.get("received_at")),
                )
            )

            if event.get("event_type") in ("entry", "exit"):
                student = db.query(Student).filter(Student.student_id == event.get("student_id")).first()
                if student:
                    parts = (event.get("beacon_uuid") or "").split("-")
                    room = parts[2] if len(parts) > 2 else "unknown"
                    status_int = 1 if event["event_type"] == "entry" else -1
                    db.add(
                        EntryLog(
                            student_id=student.student_id,
                            student_name=student.stud_name,
                            RFID=student.RFID,
                            room_value=room,
                            status=status_int,
                            timestamp=_parse_ts(event.get("received_at")),
                            confidence=0.85,
                            source="ble",
                        )
                    )
            db.commit()

    async def _process_status(self, event: Dict[str, Any]) -> None:
        with get_db_session() as db:
            device = db.query(UserDevice).filter(UserDevice.device_id == event.get("device_id")).first()
            if not device:
                return
            device.last_seen = _parse_ts(event.get("received_at"))
            device.has_rfid = bool(event.get("has_rfid"))
            device.has_pir = bool(event.get("has_pir"))
            device.has_ble = bool(event.get("has_ble"))
            device.has_camera = bool(event.get("has_camera"))
            device.ip_address = event.get("ip")
            device.firmware_version = event.get("firmware_version")
            device.status = DeviceStatusEnum.ACTIVE
            db.commit()

    async def stop(self) -> None:
        self._stop.set()
        if self.pubsub:
            try:
                await self.pubsub.unsubscribe("zias:events")
                await self.pubsub.close()
            except Exception:
                pass
        if self.redis_client:
            await self.redis_client.close()


async def _main() -> None:
    proc = EventProcessor()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(proc.stop()))
        except NotImplementedError:
            pass
    await proc.start()


if __name__ == "__main__":
    asyncio.run(_main())
