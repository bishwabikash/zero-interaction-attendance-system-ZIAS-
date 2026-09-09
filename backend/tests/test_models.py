import pytest
from pydantic import ValidationError

from api.models import (
    AttendanceEvent,
    DeviceRegister,
    DeviceType,
    Direction,
    EventType,
    RegisterRequest,
)


def test_attendance_event_confidence_bounds():
    ev = AttendanceEvent(
        student_id="ST01",
        event_type=EventType.ENTRY,
        source=DeviceType.RFID,
        location="Room 101",
        confidence=0.9,
    )
    assert ev.confidence == 0.9

    with pytest.raises(ValidationError):
        AttendanceEvent(
            student_id="ST01",
            event_type=EventType.ENTRY,
            source=DeviceType.RFID,
            location="Room 101",
            confidence=1.5,
        )


def test_device_register_defaults():
    payload = DeviceRegister(device_id="room101_in", cluster_id=101, room_value="Room 101")
    assert payload.direction == Direction.ENTRY
    assert payload.device_type == DeviceType.UNIVERSAL


def test_register_request_min_password():
    with pytest.raises(ValidationError):
        RegisterRequest(username="bob", password="short")
