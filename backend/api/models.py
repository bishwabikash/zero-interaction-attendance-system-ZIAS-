"""Pydantic API contracts."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeviceType(str, Enum):
    RFID = "rfid"
    PIR = "pir"
    BLE_BEACON = "ble_beacon"
    UNIVERSAL = "universal"


class Direction(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    BOTH = "both"


class EventType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    APPROACHING = "approaching"


class AttendanceEvent(BaseModel):
    student_id: str
    event_type: EventType
    source: DeviceType
    location: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    meta: Optional[dict] = None


class BeaconEvent(BaseModel):
    student_id: str
    beacon_uuid: str
    rssi: int
    location: Optional[dict] = None
    event_type: EventType
    app_version: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AttendanceRecord(BaseModel):
    id: int
    student_id: str
    student_name: str
    room: str
    status: str  # "entry" | "exit"
    timestamp: datetime
    confidence: float
    source: str


class AttendanceRecordList(BaseModel):
    records: List[AttendanceRecord]
    total: int


class OccupancyStudent(BaseModel):
    student_id: str
    name: str


class OccupancyResponse(BaseModel):
    room: str
    current_occupancy: int
    students: List[OccupancyStudent]
    timestamp: datetime


class StudentCreate(BaseModel):
    student_id: str
    stud_name: str
    RFID: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    class_section: Optional[str] = None


class StudentOut(StudentCreate):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime


class DeviceRegister(BaseModel):
    device_id: str
    device_type: DeviceType = DeviceType.UNIVERSAL
    direction: Direction = Direction.ENTRY
    cluster_id: int
    room_value: str
    location_description: Optional[str] = None


class DeviceHeartbeat(BaseModel):
    has_rfid: bool = False
    has_pir: bool = False
    has_ble: bool = False
    has_camera: bool = False
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None
    rssi: Optional[int] = None


class DashboardStats(BaseModel):
    total_students: int
    present_today: int
    absent_today: int
    active_devices: int


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    email: Optional[EmailStr] = None
    role: str = "viewer"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
