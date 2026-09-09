"""Devices API routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.db_models import (
    DeviceStatusEnum,
    DeviceTypeEnum,
    DirectionEnum,
    User,
    UserDevice,
)
from api.models import DeviceHeartbeat, DeviceRegister

router = APIRouter()


@router.get("/")
async def list_devices(
    cluster_id: int | None = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(UserDevice)
    if cluster_id is not None:
        query = query.filter(UserDevice.cluster_ID == cluster_id)

    devices = query.order_by(UserDevice.room_value, UserDevice.device_id).all()
    return {
        "devices": [
            {
                "device_id": d.device_id,
                "cluster_id": d.cluster_ID,
                "device_type": d.device_type.value,
                "direction": d.direction.value,
                "room": d.room_value,
                "has_rfid": bool(d.has_rfid),
                "has_pir": bool(d.has_pir),
                "has_ble": bool(d.has_ble),
                "has_camera": bool(d.has_camera),
                "status": d.status.value,
                "last_seen": d.last_seen,
                "ip": d.ip_address,
                "firmware_version": d.firmware_version,
            }
            for d in devices
        ],
        "total": len(devices),
    }


@router.post("/register", status_code=201)
async def register_device(
    device: DeviceRegister,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(UserDevice).filter(UserDevice.device_id == device.device_id).first()
    now = datetime.utcnow()

    if existing:
        existing.cluster_ID = device.cluster_id
        existing.device_type = DeviceTypeEnum(device.device_type.value)
        existing.direction = DirectionEnum(device.direction.value)
        existing.room_value = device.room_value
        existing.location_description = device.location_description
        existing.last_seen = now
        db.commit()
        return {"message": "Device updated", "device_id": device.device_id}

    db.add(
        UserDevice(
            device_id=device.device_id,
            cluster_ID=device.cluster_id,
            device_type=DeviceTypeEnum(device.device_type.value),
            direction=DirectionEnum(device.direction.value),
            room_value=device.room_value,
            location_description=device.location_description,
            status=DeviceStatusEnum.ACTIVE,
            created_at=now,
        )
    )
    db.commit()
    return {"message": "Device registered", "device_id": device.device_id}


@router.post("/{device_id}/heartbeat")
async def device_heartbeat(
    device_id: str,
    payload: DeviceHeartbeat,
    db: Session = Depends(get_db),
):
    """Public heartbeat — devices report status. Authenticated via device_id enrollment.

    NOTE: A device secret / TLS client cert should gate this in production. This
    endpoint intentionally does not require a JWT because ESP32 nodes do not have
    one; use MQTT ACLs and network isolation to protect it.
    """
    device = db.query(UserDevice).filter(UserDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not registered")

    device.last_seen = datetime.utcnow()
    device.has_rfid = payload.has_rfid
    device.has_pir = payload.has_pir
    device.has_ble = payload.has_ble
    device.has_camera = payload.has_camera
    device.ip_address = payload.ip_address
    device.firmware_version = payload.firmware_version
    device.status = DeviceStatusEnum.ACTIVE
    db.commit()

    return {"status": "ok", "device_id": device_id, "server_time": datetime.utcnow().isoformat()}
